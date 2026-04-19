# =============================================================================
# University Observatory - Worker Pipeline Test Suite
# =============================================================================

$PASS   = 0
$FAIL   = 0
$ERRORS = @()
$BASE   = "http://localhost:8000/api/v1"
$SYS    = "http://localhost:8000"

$AdminToken  = ""
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

    $params = @{
        Uri = $Url
        Method = $Method
        Headers = $headers
        UseBasicParsing = $true
        ErrorAction = "Stop"
    }

    if ($Body) {
        $params["Body"] = $Body | ConvertTo-Json -Depth 10
    }

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
                Write-Host ("Task FAILED: {0}" -f $data.error) -ForegroundColor Red
                return $null
            }

            Write-Host ("Waiting for {0}... ({1}s) status={2}" -f $Label, $elapsed, $data.status) -ForegroundColor DarkGray

        } catch { }
    }

    Write-Host ("Timed out waiting for {0} after {1}s" -f $Label, $MaxSeconds) -ForegroundColor Red
    return $null
}

# =============================================================================
# 0. Auth setup
# =============================================================================

Write-Header "0. Auth setup"

$studentEmail = "worker_test_student_$(Get-Random)@test.com"
$adminEmail   = "worker_test_admin_$(Get-Random)@test.com"

try {
    Invoke-Api POST "$BASE/auth/register" @{
        email=$studentEmail
        full_name="Worker Test Student"
        password="TestPass123!"
        academic_level="master"
        field_of_study="Computer Science"
        institution="Test University"
        interests=@("ai","machine_learning","nlp")
        skills=@("python","pytorch","sql")
        preferences=@{}
    } | Out-Null
    Pass "Register student"
} catch { Fail "Register student" $_.Exception.Message }

try {
    Invoke-Api POST "$BASE/auth/register" @{
        email=$adminEmail
        full_name="Worker Test Admin"
        password="AdminPass123!"
        academic_level="phd"
        field_of_study="Data Science"
        institution="Test University"
        interests=@("ai")
        skills=@("python")
        preferences=@{}
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
    Pass "Login admin"
} catch { Fail "Login admin" $_.Exception.Message }

# =============================================================================
# 1. Seed opportunities
# =============================================================================

Write-Header "1. Seed opportunities"

$testOpps = @(
    @{
        title="AI Research Internship - NLP $(Get-Random)"
        description="NLP internship"
        organization="INRIA"
        source="test"
        url="https://example.com/1"
        type="internship"
        domain="nlp"
        level="master"
        location_type="remote"
        required_skills=@("python","pytorch")
        tags=@("nlp")
        is_paid=$true
        stipend_amount=1000
        stipend_currency="EUR"
        eligibility=@{}
        raw_data=@{}
        scraper_type="static"
    },
    @{
        title="PhD Computer Vision $(Get-Random)"
        description="PhD CV"
        organization="ETH Zurich"
        source="test"
        url="https://example.com/2"
        type="scholarship"
        domain="computer_vision"
        level="phd"
        location_type="onsite"
        required_skills=@("python")
        tags=@("cv")
        is_paid=$true
        stipend_amount=2000
        stipend_currency="CHF"
        eligibility=@{}
        raw_data=@{}
        scraper_type="static"
    }
)

$OppIds = @()

foreach ($opp in $testOpps) {
    try {
        $r = Invoke-Api POST "$BASE/opportunities/" $opp $AdminToken
        $id = ($r.Content | ConvertFrom-Json).id
        $OppIds += $id
        Pass "Seeded $($opp.title)"
    } catch {
        Fail "Seed opportunity" $_.Exception.Message
    }
}

# =============================================================================
# 2. Classifier
# =============================================================================

Write-Header "2. Classifier"

try {
$py = @"
import sys, os
sys.path.insert(0, 'backend')
from backend.queue.producer import enqueue_classifier
r = enqueue_classifier()
print(r.id)
"@

    $taskId = (python -c $py).Trim()
    $res = Wait-TaskComplete $taskId 120 "classifier"

    if ($res) { Pass "Classifier ran" }
    else { Fail "Classifier" "no result" }

} catch { Fail "Classifier" $_.Exception.Message }

# =============================================================================
# 3. Cluster
# =============================================================================

Write-Header "3. Cluster"

try {
$py = @"
import sys, os
sys.path.insert(0, 'backend')
from backend.queue.producer import enqueue_cluster_recompute
r = enqueue_cluster_recompute()
print(r.id)
"@

    $taskId = (python -c $py).Trim()
    $res = Wait-TaskComplete $taskId 180 "cluster"

    if ($res) { Pass "Cluster ran" }
    else { Fail "Cluster" "no result" }

} catch { Fail "Cluster" $_.Exception.Message }

# =============================================================================
# 4. Recommendations
# =============================================================================

Write-Header "4. Recommendations"

try {
$py = @"
import sys, os
sys.path.insert(0, 'backend')
from backend.queue.producer import enqueue_recommendation_recompute
r = enqueue_recommendation_recompute()
print(r.id)
"@

    $taskId = (python -c $py).Trim()
    $res = Wait-TaskComplete $taskId 180 "recommendations"

    if ($res) { Pass "Recommendations ran" }
    else { Fail "Recommendations" "no result" }

} catch { Fail "Recommendations" $_.Exception.Message }

# =============================================================================
# Summary
# =============================================================================

$total = $PASS + $FAIL

Write-Host ""
Write-Host "======================================="
Write-Host "Results: $PASS / $total passed"
Write-Host "======================================="

if ($ERRORS.Count -gt 0) {
    Write-Host "Failures:"
    foreach ($e in $ERRORS) { Write-Host $e }
}

if ($FAIL -gt 0) { exit 1 }