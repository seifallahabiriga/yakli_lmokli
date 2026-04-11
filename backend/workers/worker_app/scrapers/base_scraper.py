class BaseScraper:
    def run(self) -> list[dict]:
        raise NotImplementedError("Each scraper must implement its own run method")
