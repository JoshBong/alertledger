"""The fixed category taxonomy. Few and human, so the donut stays readable. rules.toml maps merchants into these;
bank-supplied categories (Chase CSV) are mapped through BANK_MAP."""
CATEGORIES = ["Food & Dining", "Groceries", "Shopping", "Travel", "Transport", "Bills & Subscriptions", "Health", "People", "Other"]
OTHER = "Other"

# bank category → ours
BANK_MAP = {
    "food & drink": "Food & Dining", "restaurants": "Food & Dining", "dining": "Food & Dining",
    "groceries": "Groceries", "grocery": "Groceries",
    "shopping": "Shopping", "entertainment": "Shopping", "gifts & donations": "Shopping", "personal": "Shopping",
    "travel": "Travel", "lodging": "Travel", "airlines": "Travel",
    "gas": "Transport", "automotive": "Transport", "transportation": "Transport",
    "bills & utilities": "Bills & Subscriptions", "utilities": "Bills & Subscriptions", "subscriptions": "Bills & Subscriptions",
    "professional services": "Bills & Subscriptions", "education": "Bills & Subscriptions", "fees & adjustments": "Bills & Subscriptions",
    "health & wellness": "Health", "healthcare": "Health", "pharmacy": "Health",
}


def normalize(cat: str | None) -> str:
    if not cat:
        return OTHER
    if cat in CATEGORIES:
        return cat
    return BANK_MAP.get(cat.strip().lower(), OTHER)
