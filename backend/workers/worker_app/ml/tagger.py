import logging
from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def extract_tags(title: str, description: str) -> set[str]:
    try:
        import spacy
        nlp = spacy.load(settings.SPACY_MODEL)
        doc = nlp(f"{title}. {description[:1000]}")

        tags: set[str] = set()

        for ent in doc.ents:
            if ent.label_ in ("ORG", "GPE", "PRODUCT"):
                tags.add(ent.text.lower().strip())

        for chunk in doc.noun_chunks:
            token = chunk.root
            if not token.is_stop and not token.is_punct and len(chunk.text) > 3:
                tags.add(chunk.text.lower().strip())

        return tags
    except Exception as exc:
        logger.warning(f"spaCy tag extraction failed: {exc}")
        return set()
