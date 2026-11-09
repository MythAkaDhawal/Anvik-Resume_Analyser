"""In-memory skill search index, n-gram scanning, and confusable checking (FR-05, FR-10).

Builds O(1) alias-to-canonical dictionaries, tokenises resume body text for
multi-word taxonomy skill matching, and provides symmetric confusable pair checks.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from resume_analyzer.skills.normalizer import normalize_skill
from resume_analyzer.skills.taxonomy import SkillTaxonomy

logger = logging.getLogger(__name__)

# Tokenization regex per TECHNICAL_SPECIFICATION §6.4:
# Matches tokens starting with optional dot or alphanumeric, followed by alphanumeric, +, #, ., -
TOKEN_REGEX = re.compile(r"\.?[a-zA-Z0-9][a-zA-Z0-9+#.\-]*")


class SkillIndex:
    """Precomputed in-memory index over SkillTaxonomy for high-throughput scanning.

    Attributes:
        taxonomy: Underlying SkillTaxonomy instance.
        fuzzy_enabled: Whether fuzzy matching is active.
        fuzzy_threshold: Minimum similarity threshold (default 85.0).
        fuzzy_min_length: Minimum token length required for fuzzy comparison.
    """

    def __init__(
        self,
        taxonomy: SkillTaxonomy,
        fuzzy_enabled: bool = True,
        fuzzy_threshold: float = 85.0,
        fuzzy_min_length: int = 4,
    ) -> None:
        """Initialize and pre-index taxonomy aliases, categories, and confusables."""
        self.taxonomy = taxonomy
        self.fuzzy_enabled = fuzzy_enabled
        self.fuzzy_threshold = fuzzy_threshold
        self.fuzzy_min_length = fuzzy_min_length

        self.alias_to_canonical: dict[str, str] = {}
        self.canonical_set: set[str] = set()
        self.category_by_canonical: dict[str, str] = {}
        self._confusable_set: set[frozenset[str]] = set()

        max_tokens = 1
        for entry in taxonomy.skills:
            can = entry.canonical
            self.canonical_set.add(can)
            self.category_by_canonical[can] = entry.category

            can_norm = normalize_skill(can)
            self.alias_to_canonical[can_norm] = can
            tokens_count = len(can_norm.split())
            if tokens_count > max_tokens:
                max_tokens = tokens_count

            for alias in entry.aliases:
                a_norm = normalize_skill(alias)
                self.alias_to_canonical[a_norm] = can
                a_tokens = len(a_norm.split())
                if a_tokens > max_tokens:
                    max_tokens = a_tokens

        # Cap max_ngram at 4 per specification
        self.max_ngram = min(max_tokens, 4)

        # Index confusable pairs symmetrically using frozensets of normalized strings
        for pair in taxonomy.confusable_pairs:
            if len(pair) == 2:
                p1_norm = normalize_skill(pair[0])
                p2_norm = normalize_skill(pair[1])
                self._confusable_set.add(frozenset([p1_norm, p2_norm]))

    @property
    def categories(self) -> list[str]:
        """Return the declared taxonomy category names."""
        return self.taxonomy.categories

    def canonical(self, norm_text: str) -> str | None:
        """Return the canonical skill name for a normalized string or alias, or None."""
        return self.alias_to_canonical.get(norm_text)

    def get_canonical(self, norm_text: str) -> str | None:
        """Alias for canonical()."""
        return self.canonical(norm_text)

    def category(self, canonical_name: str) -> str | None:
        """Return the taxonomy category for a canonical skill name."""
        return self.category_by_canonical.get(canonical_name)

    def get_category(self, canonical_name: str) -> str | None:
        """Alias for category()."""
        return self.category(canonical_name)

    def is_confusable(self, a: str, b: str) -> bool:
        """Check whether two skills are declared as confusable pairs."""
        a_norm = normalize_skill(a)
        b_norm = normalize_skill(b)
        return frozenset([a_norm, b_norm]) in self._confusable_set

    def find_mentions(self, text: str) -> Counter[str]:
        """Scan free-form text using n-grams and return canonical mention counts.

        Extracts tokens, evaluates 1-to-max_ngram combinations against the taxonomy,
        and aggregates occurrences.

        Args:
            text: Arbitrary section text or body text.

        Returns:
            Counter mapping canonical skill names to occurrence counts.
        """
        counts: Counter[str] = Counter()
        if not text:
            return counts

        raw_tokens = TOKEN_REGEX.findall(text)
        cleaned_tokens: list[str] = []
        for t in raw_tokens:
            cleaned = t.rstrip(".-").lower()
            if cleaned:
                cleaned_tokens.append(cleaned)

        num_tokens = len(cleaned_tokens)
        alias_map = self.alias_to_canonical

        # 1-grams (avoid string slicing and join overhead)
        for tok in cleaned_tokens:
            canonical_name = alias_map.get(tok)
            if canonical_name:
                counts[canonical_name] += 1

        # Multi-word n-grams (2 to max_ngram)
        for n in range(2, self.max_ngram + 1):
            for i in range(num_tokens - n + 1):
                ngram_str = " ".join(cleaned_tokens[i : i + n])
                canonical_name = alias_map.get(ngram_str)
                if canonical_name:
                    counts[canonical_name] += 1

        return counts


@lru_cache(maxsize=4)
def get_skill_index(taxonomy_path: Path | str) -> SkillIndex:
    """Load and index a SkillTaxonomy from a JSON file with LRU caching."""
    tax = SkillTaxonomy.from_file(taxonomy_path)
    return SkillIndex(taxonomy=tax)
