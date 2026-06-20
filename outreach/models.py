from dataclasses import dataclass, field

SIGNALS = [
    "no_website", "social_only", "site_unreachable", "weak_google",
    "no_contact_button", "no_service_pages", "outdated_website", "bad_mobile",
    "broken_links", "old_photos",
]

@dataclass
class Business:
    place_id: str
    name: str
    category: str = ""
    town: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""          # "" if none; may be an IG/FB url
    email: str = ""            # scraped if found
    instagram: str = ""        # profile url if found
    facebook: str = ""         # profile url if found
    rating: float = 0.0
    review_count: int = 0
    business_status: str = "OPERATIONAL"
    social_confidence: str = ""   # "high" | "low" | "" (set by social lookup)

@dataclass
class Findings:
    no_website: bool = False
    social_only: bool = False
    weak_google: bool = False
    no_contact_button: bool = False
    no_service_pages: bool = False
    outdated_website: bool = False
    bad_mobile: bool = False
    broken_links: bool = False
    old_photos: bool = False
    site_unreachable: bool = False
    details: dict = field(default_factory=dict)

    def fired(self):
        return [s for s in SIGNALS if getattr(self, s)]

@dataclass
class Lead:
    business: Business
    findings: Findings
    score: int
    summary: str
    channel: str = ""          # email | dm | phone | none
    subject: str = ""
    draft: str = ""
