# Canonical outreach copy in Tanner's voice. {name} = business name.
# Keys map to the primary problem; "default" is the fallback.

DM_TEMPLATES = {
    "no_website": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean websites for small businesses on the side. "
        "I came across {name} and noticed you may not have a dedicated website yet. "
        "I'm currently offering a free website sample upon request, so you can see what "
        "your business could look like online before committing to anything. Would you "
        "like me to put together a sample for you?"
    ),
    "outdated_website": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I checked out {name}'s current website and I think I could help make it look "
        "more modern, easier to use, and better at getting customers to contact you. "
        "I'm offering a free website sample upon request if you'd like to see what a "
        "cleaner version could look like."
    ),
    "social_only": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter helping small businesses build clean, professional websites. "
        "{name}'s Instagram looks solid, but having a website can make it easier for "
        "customers to find your services, prices, photos, contact info, and book with "
        "you. I'm offering a free website sample upon request if you'd like to see what "
        "your business could look like online."
    ),
    "weak_google": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter who builds clean websites for small businesses on the side. "
        "I came across {name} and a solid website would help more local customers find "
        "and trust you when they search. I'm offering a free website sample upon request "
        "so you can see what it could look like - no commitment."
    ),
    "no_contact_button": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I looked at {name}'s site and noticed it's hard for customers to reach you "
        "quickly. I'd love to help make it easier for people to call, message, or book. "
        "I'm offering a free website sample upon request if you'd like to see what a "
        "cleaner version could look like."
    ),
    "default": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I came across {name} and think a refreshed website could help you reach more "
        "customers. I'm offering a free website sample upon request - no commitment. "
        "Would you like me to put one together for you?"
    ),
}

EMAIL_SUBJECTS = {
    "no_website": "A free website sample for {name}",
    "outdated_website": "A cleaner website for {name} (free sample)",
    "social_only": "A website to go with {name}'s Instagram (free sample)",
    "weak_google": "Helping {name} get found online (free sample)",
    "no_contact_button": "Making it easier for {name}'s customers to reach you",
    "default": "A free website sample for {name}",
}

EMAIL_SIGNATURE = (
    "\n\nMahalo,\nTanner\nFrontline Web Designs\nfrontlinewebdesign.tech\n"
)

# CAN-SPAM opt-out line appended to emails only.
EMAIL_OPTOUT = (
    "\n\n---\nYou're receiving this because you run a local Maui business. "
    "If you'd rather not hear from me, just reply \"not interested\" and I won't "
    "follow up.\nFrontline Web Designs, Maui, HI"
)
