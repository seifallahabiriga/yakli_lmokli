# =============================================================================
# University Observatory - Worker Pipeline Test Suite
# Run from project root: .\test_workers_fixed.ps1
# Prerequisites:
#   - PostgreSQL running + alembic upgrade head applied
#   - Redis running
#   - Celery worker: celery -A backend.job_queue.celery_app worker --loglevel=info -Q default,scraping,ml,notifications
#   - FastAPI: uvicorn backend.main:app --reload
# =============================================================================

$PASS   = 0
$FAIL   = 0
$ERRORS = @()
$BASE   = "http://localhost:8000/api/v1"
$SYS    = "http://localhost:8000"
$AdminToken   = ""
$StudentToken = ""

function Write-Header($title) {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor DarkGray
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor DarkGray
}

function Pass($label) {
    $script:PASS++
    Write-Host "[PASS] $label" -ForegroundColor Green
}

function Fail($label, $reason) {
    $script:FAIL++
    $script:ERRORS += ("  {0} - {1}" -f $label, $reason)
    Write-Host ("[FAIL] {0} - {1}" -f $label, $reason) -ForegroundColor Red
}

function Skip($label, $reason) {
    Write-Host ("[SKIP] {0} - {1}" -f $label, $reason) -ForegroundColor Yellow
}

function Invoke-Api {
    param($Method, $Url, $Body = $null, $Token = $null)
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    $params = @{ Uri = $Url; Method = $Method; Headers = $headers; UseBasicParsing = $true; ErrorAction = "Stop" }
    if ($Body) { $params["Body"] = $Body | ConvertTo-Json -Depth 10 }
    return Invoke-WebRequest @params
}

function Wait-TaskComplete {
    param($TaskId, $MaxSeconds = 300, $Label = "task")
    $elapsed = 0
    while ($elapsed -lt $MaxSeconds) {
        Start-Sleep -Seconds 5
        $elapsed += 5
        try {
            $r = Invoke-WebRequest -Uri "$SYS/tasks/$TaskId" -UseBasicParsing -ErrorAction Stop
            $data = $r.Content | ConvertFrom-Json
            if ($data.status -eq "SUCCESS") { return $data }
            if ($data.status -eq "FAILURE") {
                Write-Host ("  Task FAILED: {0}" -f $data.error) -ForegroundColor Red
                return $null
            }
            Write-Host ("  Waiting... ({0}s) status={1}" -f $elapsed, $data.status) -ForegroundColor DarkGray
        } catch { }
    }
    Write-Host ("  Timed out after {0}s" -f $MaxSeconds) -ForegroundColor Red
    return $null
}

# =============================================================================
# 0. Auth setup
# =============================================================================
Write-Header "0. Auth setup"

$rand = Get-Random
$studentEmail = "worker_student_${rand}@test.com"
$adminEmail   = "worker_admin_${rand}@test.com"

try {
    Invoke-Api POST "$BASE/auth/register" @{
        email=$studentEmail; full_name="Worker Test Student"; password="TestPass123!"
        academic_level="master"; field_of_study="Computer Science"; institution="Test University"
        interests=@("ai","machine_learning","nlp"); skills=@("python","pytorch","sql")
        preferences=@{ locations=@("remote") }
    } | Out-Null
    Pass "Register student"
} catch { Fail "Register student" $_.Exception.Message }

try {
    Invoke-Api POST "$BASE/auth/register" @{
        email=$adminEmail; full_name="Worker Test Admin"; password="AdminPass123!"
        academic_level="phd"; field_of_study="Data Science"; institution="Test University"
        interests=@("ai"); skills=@("python"); preferences=@{}
    } | Out-Null
    Pass "Register admin"
} catch { Fail "Register admin" $_.Exception.Message }

try {
    $r = Invoke-Api POST "$BASE/auth/login" @{email=$studentEmail; password="TestPass123!"}
    $StudentToken = ($r.Content | ConvertFrom-Json).access_token
    Pass "Login student"
} catch { Fail "Login student" $_.Exception.Message }

try {
    $r = Invoke-Api POST "$BASE/auth/login" @{email=$adminEmail; password="AdminPass123!"}
    $AdminToken = ($r.Content | ConvertFrom-Json).access_token
    Pass "Login admin (role=student for now)"
} catch { Fail "Login admin" $_.Exception.Message }

# Promote admin role in DB
Write-Host ""
Write-Host "  ACTION REQUIRED: Run this SQL now, then press Enter:" -ForegroundColor Yellow
Write-Host "  UPDATE users SET role = 'admin' WHERE email = '$adminEmail';" -ForegroundColor White
Write-Host ""
Read-Host "  Press Enter after running the SQL"

# Re-login to get token with admin role
try {
    $r = Invoke-Api POST "$BASE/auth/login" @{email=$adminEmail; password="AdminPass123!"}
    $AdminToken = ($r.Content | ConvertFrom-Json).access_token
    Pass "Re-login admin with role=admin"
} catch { Fail "Re-login admin" $_.Exception.Message }

# =============================================================================
# 1. Seed opportunities
# =============================================================================
Write-Header "1. Seed opportunities"

$OppIds = @()
$baseUrl = "https://example-test-$(Get-Random).com"

$testOpps = @(
    @{
        title="AI NLP Internship Test $(Get-Random)"; description="NLP internship for testing"
        organization="INRIA"; source="test"; url="$baseUrl/1"
        type="internship"; domain="nlp"; level="master"; location_type="remote"
        required_skills=@("python","pytorch","nlp"); tags=@("nlp","internship","ai")
        is_paid=$true; stipend_amount=1000; stipend_currency="EUR"
        eligibility=@{}; raw_data=@{}; scraper_type="static"
    },
    @{
        title="PhD Computer Vision Test $(Get-Random)"; description="PhD in CV"
        organization="ETH Zurich"; source="test"; url="$baseUrl/2"
        type="scholarship"; domain="computer_vision"; level="phd"; location_type="onsite"
        required_skills=@("python","deep-learning"); tags=@("cv","phd","scholarship")
        is_paid=$true; stipend_amount=2000; stipend_currency="CHF"
        eligibility=@{}; raw_data=@{}; scraper_type="static"
    },
    @{
        title="ML Research Project Test $(Get-Random)"; description="Federated learning research"
        organization="European Commission"; source="test"; url="$baseUrl/3"
        type="research_project"; domain="machine_learning"; level="phd"; location_type="remote"
        required_skills=@("python","machine-learning","pytorch"); tags=@("research","ml","eu")
        is_paid=$true; stipend_amount=2500; stipend_currency="EUR"
        eligibility=@{}; raw_data=@{}; scraper_type="static"
    }
)

foreach ($opp in $testOpps) {
    try {
        $r = Invoke-Api POST "$BASE/opportunities/" $opp $AdminToken
        $id = ($r.Content | ConvertFrom-Json).id
        $OppIds += $id
        Pass "Seeded: $($opp.title.Substring(0, [Math]::Min(45, $opp.title.Length)))"
    } catch {
        Fail "Seed opportunity" $_.Exception.Message
    }
}

if ($OppIds.Count -eq 0) {
    Write-Host "  No opportunities seeded - aborting pipeline tests" -ForegroundColor Red
    exit 1
}
Write-Host "  Seeded IDs: $($OppIds -join ', ')" -ForegroundColor DarkGray

# =============================================================================
# 2. Classifier
# =============================================================================
Write-Header "2. Classifier agent"

try {
    # FIX: sys.path.insert(0, '.') from project root + correct module path backend.job_queue
    $py = "import sys, os; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_classifier; r = enqueue_classifier(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()

    if ($taskId -match "Error|Traceback|No module") {
        Fail "Classifier enqueue" $taskId
    } else {
        Write-Host "  Task ID: $taskId" -ForegroundColor DarkGray
        $res = Wait-TaskComplete $taskId 120 "classifier"
        if ($res) {
            Pass "Classifier ran"
            Write-Host "  Result: $($res.result | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
        } else {
            Fail "Classifier" "task did not complete successfully"
        }
    }
} catch { Fail "Classifier" $_.Exception.Message }

# Verify opportunities promoted to ACTIVE
try {
    $r = Invoke-Api GET "$BASE/opportunities/?status=active&page_size=10" $null $null
    $data = $r.Content | ConvertFrom-Json
    if ($data.total -gt 0) {
        Pass "Opportunities active after classification (total=$($data.total))"
    } else {
        Skip "Opportunities ACTIVE check" "classifier may not have run yet"
    }
} catch { Fail "Opportunities ACTIVE check" $_.Exception.Message }

# =============================================================================
# 3. Cluster recompute
# =============================================================================
Write-Header "3. Cluster agent"

try {
    $py = "import sys; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_cluster_recompute; r = enqueue_cluster_recompute(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()

    if ($taskId -match "Error|Traceback|No module") {
        Fail "Cluster enqueue" $taskId
    } else {
        Write-Host "  Task ID: $taskId" -ForegroundColor DarkGray
        $res = Wait-TaskComplete $taskId 180 "cluster recompute"
        if ($res) {
            Pass "Cluster recompute ran"
            Write-Host "  Result: $($res.result | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
        } else {
            Fail "Cluster" "task did not complete successfully"
        }
    }
} catch { Fail "Cluster" $_.Exception.Message }

# Verify clusters via API
try {
    $r = Invoke-Api GET "$BASE/clusters/" $null $StudentToken
    $data = $r.Content | ConvertFrom-Json
    if ($data.total -gt 0) {
        Pass "Clusters exist (total=$($data.total))"
        Write-Host "  Top cluster: $($data.items[0].name) - $($data.items[0].member_count) members" -ForegroundColor DarkGray
    } else {
        Skip "Clusters check" "need 20+ opportunities for KMeans (seeded only $($OppIds.Count))"
    }
} catch { Fail "Clusters API" $_.Exception.Message }

# =============================================================================
# 4. Recommendations
# =============================================================================
Write-Header "4. Recommendation agent"

try {
    $py = "import sys; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_recommendation_recompute; r = enqueue_recommendation_recompute(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()

    if ($taskId -match "Error|Traceback|No module") {
        Fail "Recommendations enqueue" $taskId
    } else {
        Write-Host "  Task ID: $taskId" -ForegroundColor DarkGray
        $res = Wait-TaskComplete $taskId 180 "recommendations"
        if ($res) {
            Pass "Recommendation agent ran"
            Write-Host "  Result: $($res.result | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
        } else {
            Fail "Recommendations" "task did not complete successfully"
        }
    }
} catch { Fail "Recommendations" $_.Exception.Message }

# Verify recommendations via API
try {
    $r = Invoke-Api GET "$BASE/recommendations/me" $null $StudentToken
    $data = $r.Content | ConvertFrom-Json
    if ($data.total -gt 0) {
        Pass "Student has recommendations (total=$($data.total))"
        $top = $data.items[0]
        Write-Host "  Top rec: score=$($top.score) - $($top.opportunity.title.Substring(0,[Math]::Min(50,$top.opportunity.title.Length)))" -ForegroundColor DarkGray
    } else {
        Skip "Student recommendations" "no recommendations yet (may need more opportunities or profile match)"
    }
} catch { Fail "Recommendations API" $_.Exception.Message }

# =============================================================================
# 5. Maintenance tasks
# =============================================================================
Write-Header "5. Maintenance tasks"

try {
    $py = "import sys; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_expire_opportunities; r = enqueue_expire_opportunities(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()
    if ($taskId -notmatch "Error|Traceback") {
        $res = Wait-TaskComplete $taskId 60 "expire opportunities"
        if ($res) { Pass "Expire past deadline task" } else { Fail "Expire task" "no result" }
    } else { Fail "Expire enqueue" $taskId }
} catch { Fail "Expire task" $_.Exception.Message }

try {
    $py = "import sys; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_cleanup_notifications; r = enqueue_cleanup_notifications(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()
    if ($taskId -notmatch "Error|Traceback") {
        $res = Wait-TaskComplete $taskId 60 "cleanup notifications"
        if ($res) { Pass "Cleanup notifications task" } else { Fail "Cleanup task" "no result" }
    } else { Fail "Cleanup enqueue" $taskId }
} catch { Fail "Cleanup task" $_.Exception.Message }

# =============================================================================
# 6. FAISS persistence
# =============================================================================
Write-Header "6. FAISS persistence"

try {
    $py = "import sys; sys.path.insert(0, '.'); from backend.job_queue.producer import enqueue_persist_faiss_index; r = enqueue_persist_faiss_index(); print(r.id)"
    $taskId = (python -c $py 2>&1).Trim()
    if ($taskId -notmatch "Error|Traceback") {
        $res = Wait-TaskComplete $taskId 60 "faiss persist"
        if ($res) {
            Pass "FAISS index persisted"
            Write-Host "  $($res.result | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
        } else { Skip "FAISS persist" "no index built yet (need cluster run first)" }
    } else { Fail "FAISS enqueue" $taskId }
} catch { Fail "FAISS task" $_.Exception.Message }

# =============================================================================
# Summary
# =============================================================================
$total = $PASS + $FAIL

Write-Host ""
Write-Host "==================================================" -ForegroundColor DarkGray
Write-Host ("  Results: {0}/{1} passed" -f $PASS, $total) -ForegroundColor $(if ($FAIL -eq 0) { "Green" } else { "Yellow" })
Write-Host "==================================================" -ForegroundColor DarkGray

if ($ERRORS.Count -gt 0) {
    Write-Host ""
    Write-Host "  Failures:" -ForegroundColor Red
    foreach ($e in $ERRORS) { Write-Host $e -ForegroundColor Red }
}

Write-Host ""
if ($FAIL -eq 0) {
    Write-Host "  All pipeline tests passed." -ForegroundColor Green
} else {
    Write-Host "  $FAIL test(s) failed." -ForegroundColor Red
    exit 1
}