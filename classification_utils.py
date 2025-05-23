import urllib.request
import json
import re
from config import OLLAMA_URL, MODEL_NAME, CONTENT_CATS, OLLAMA_HOST, OLLAMA_PORT
import time
import socket
print("[DEBUG] classification_utils.py loaded.")

# —— 丰富的邮件分类主 Prompt ——  
MAIN_PROMPT = r"""
[System Command]
You are a smart email classification assistant. Please strictly complete a single main category judgment for the following email:
The category must strictly be selected from the following eight categories (no new categories, no plural form, no spaces, no case errors):

"Work"          —— Directly related to current work/project (such as project emails, colleague collaboration, task assignment, etc.)
"Personal"      —— Family/friend private letters or social network notifications, also including travel, tickets, etc. personal consumption
"Transaction"   —— Orders, invoices, bills, express, payment, receipt, etc.
"Promotion"     —— Merchant/platform promotions, advertisements, coupons, subscription push
"Security"      —— Login verification code, account exception alarm, email confirmation/verification, security reminder, etc.
"Update"        —— System or product function update, version release, function optimization, service change
"Opportunities" —— Job opportunities, recruitment information, position invitation, interview notification, etc.
"LowPriority"   —— Other low-priority notifications, general system emails, miscellaneous, or situations that cannot be categorized into any of the above

【Output Requirements】
- Only output and **only output** the following JSON format, no extra characters, explanations, explanations, line breaks, or comments!
- Format must be: {{"category":"Category Name"}}
- Category name must strictly be one of the above eight categories, otherwise it is considered invalid.

【Strict Classification Logic】
- If the sender is on the blacklist (such as: Otter.ai, Gumtree, Everyday Rewards, Telstra Team, Prosple, Academia, 13cabs, Flybuys, DoorDash, email addresses containing Promotions@, No-Reply@, Unsubscribe@, etc.), regardless of content, directly classify as {{"category":"Promotion"}}
- Emails from bigfamily are always {{"category":"Security"}}
- Bandmix defaults to Promotion, only select Personal if the dialog content is clearly private
- LinkedIn, new job post, gradconnect, seek, hays, etc. Job-related platforms, if they are clearly involved in interviews/invitations/positions, they are {{"category":"Opportunities"}}, otherwise they are Promotion
Special attention should be paid to LinkedIn, unless it is really receiving opportunities from enterprises, otherwise it should be classified as Promotion
- If the subject or body contains verification code, secondary verification, login, security reminder, etc., prioritize Security
- Orders, payments, express, bills, etc. prioritize Transaction
- Advertisements, promotions, discounts, pushes prioritize Promotion
- If it is really impossible to determine, it defaults to LowPriority

—— Original Email Data ——  
From: {from_addr}  
Subject: {subject}  
Body:  
{body}
"""

def safe_category(cat):
    """Prevent classification spelling/space etc. small errors"""
    if not cat:
        return ""
    cat = cat.strip().capitalize()
    # Compatible with lowercase, plural, etc.
    fixes = {
        "Promotions": "Promotion",
        "Updates": "Update",
        "Transactions": "Transaction",
        "Opportunitie": "Opportunities", # Prevent model missing s
        "Opportunites": "Opportunities",
        "Work ": "Work",
        "Personal ": "Personal",
        "Transaction ": "Transaction",
        "Promotion ": "Promotion",
        "Security ": "Security",
        "Update ": "Update",
        "Opportunities ": "Opportunities",
        "Lowpriority": "LowPriority",
        "Lowpriority ": "LowPriority",
    }
    if cat in fixes:
        cat = fixes[cat]
    if cat in CONTENT_CATS:
        return cat
    return ""

def compose_email_data(body, headers):
    """Assemble email data for use in prompts"""
    return f"""From: {headers.get('From', '')}
Subject: {headers.get('Subject', '')}
Body:
{body}
"""

def classify_main(body: str, headers: dict) -> str:
    """
    Email classification main function, call order:
    1. Priority use Ollama API for classification
    2. If API fails, use simple rule-based classification
    3. If both fail, return default category LowPriority
    """
    from_addr = headers.get("From", "").lower()
    subject = headers.get("Subject", "").lower()
    body_lower = body.lower() if body else ""
    
    # First try to use API for classification
    max_retries = 2  # Maximum retry times
    retry_count = 0
    timeout_seconds = 10  # Set 10 seconds timeout
    
    while retry_count <= max_retries:
        try:
            print(f"[INFO] Attempting classification via Ollama API{' (Retry #'+str(retry_count)+')' if retry_count > 0 else ''}")
            print(f"[DEBUG] API URL: {OLLAMA_URL}")
            print(f"[DEBUG] Model: {MODEL_NAME}")

            # Limit email body size to avoid excessive requests
            max_body_chars = 7000
            truncated_body = body[:max_body_chars] if body and len(body) > max_body_chars else body
            if body and len(body) > max_body_chars:
                print(f"[DEBUG] Email body truncated to {max_body_chars} characters.")

            # Assemble API request
            payload = {
                "model": MODEL_NAME,
                "prompt": MAIN_PROMPT.format(
                    from_addr=headers.get("From",""),
                    subject=headers.get("Subject",""),
                    body=truncated_body
                ),
                "stream": False
            }
            data = json.dumps(payload).encode()

            print(f"[DEBUG] Sending API request...")
            req = urllib.request.Request(
                OLLAMA_URL,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            # Set timeout time
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status_code = resp.status
                print(f"[DEBUG] API response status: {status_code}")
                response_data = json.loads(resp.read().decode())
                text = response_data.get("response", "").strip()
                print(f"[DEBUG] API raw response: {text}")

                # Try to parse JSON directly
                cat = ""
                try:
                    obj = json.loads(text)
                    cat = obj.get("category", "")
                except Exception as je:
                    print(f"[DEBUG] JSON parse failed: {str(je)}")

                    # Regex fallback: extract {"category":"xxx"}
                    m = re.search(r'\{\s*"category"\s*:\s*"([A-Za-z]+)"\s*\}', text)
                    if m:
                        cat = m.group(1)
                        print(f"[INFO] Category extracted via regex: {cat}")
                    else:
                        print(f"[ERROR] No category field found in LLM response.")
                        cat = ""

                cat = safe_category(cat)
                print(f"[DEBUG] Normalized category: {cat}")

                if cat in CONTENT_CATS:
                    print(f"[INFO] Ollama API classification: {cat}")
                    return cat
                else:
                    print(f"[DEBUG] Invalid category value '{cat}', not in allowed list.")
            
            # If here, API call succeeded but no valid category, exit retry loop
            break

        except urllib.error.HTTPError as e:
            print(f"[INFO] Ollama API HTTP error: {e.code} {e.reason}")
            print(f"[DEBUG] Exception: HTTPError")
            retry_count += 1
            if retry_count <= max_retries:
                print(f"[INFO] Retrying in 1 second...")
                time.sleep(1)
            continue

        except urllib.error.URLError as e:
            print(f"[INFO] Ollama API network error: {str(e)}")
            print(f"[DEBUG] Exception: URLError")
            retry_count += 1
            if retry_count <= max_retries:
                print(f"[INFO] Retrying in 1 second...")
                time.sleep(1)
            continue

        except socket.timeout:
            print(f"[INFO] Ollama API request timed out.")
            print(f"[DEBUG] Exception: socket.timeout")
            retry_count += 1
            if retry_count <= max_retries:
                print(f"[INFO] Retrying in 1 second...")
                time.sleep(1)
            continue

        except Exception as e:
            print(f"[INFO] Ollama API call failed: '{str(e)[:100]}'...")
            print(f"[DEBUG] Exception: {type(e).__name__}")
            retry_count += 1
            if retry_count <= max_retries:
                print(f"[INFO] Retrying in 1 second...")
                time.sleep(1)
            continue

    # API call failed or result invalid, use rule-based classification
    print(f"[INFO] Fallback to rule-based classification.")
    
    # Blacklist check - classify as Promotion
    blacklist = [
        "otter.ai", "everyday rewards", "telstra", "gumtree", "prosple", "academia",
        "13cabs", "flybuys", "doordash", "promotions@", "no-reply@", "unsubscribe@",
        "noreply@", "notifications@", "newsletter@", "marketing@", "bandmix",
        "advertisement", "promotion", "discount", "sale", "off", "coupon"
    ]

    if any(term in from_addr for term in blacklist):
        match = next((term for term in blacklist if term in from_addr), None)
        print(f"[INFO] Blacklist sender match: '{match}' -> Promotion")
        return "Promotion"
    
    # Security category keywords
    security_terms = [
        "security", "verification code", "login", "password", "bigfamily",
        "account", "security", "confirm", "authenticate", "secondary verification", "2fa", 
        "identity verification", "secure", "authentication", "alert", "warning", "suspicious"
    ]
    
    for term in security_terms:
        if term in subject:
            print(f"[INFO] Security keyword match (subject): '{term}' -> Security")
            return "Security"
        if term in from_addr:
            print(f"[INFO] Security keyword match (sender): '{term}' -> Security")
            return "Security"
        if term in body_lower[:500]:
            print(f"[INFO] Security keyword match (body): '{term}' -> Security")
            return "Security"
    
    # Opportunities category keywords
    opportunity_terms = [
        "job", "career", "opportunity", "position", "interview", "hire", "recruitment",
        "application", "resume", "position", "recruitment", "offer", "employment", "hiring",
        "talent", "apply", "candidate", "job opening", "job opportunities", "career development"
    ]
    
    for term in opportunity_terms:
        if term in subject:
            print(f"[INFO] Opportunity keyword match (subject): '{term}' -> Opportunities")
            return "Opportunities"
        if term in body_lower[:500]:
            print(f"[INFO] Opportunity keyword match (body): '{term}' -> Opportunities")
            return "Opportunities"
    
    # Work category keywords
    work_terms = [
        "urgent", "important", "action", "required", "please note", "urgent", 
        "deadline", "payment", "invoice", "contract", "project", "task",
        "meeting", "report", "work", "project", "task", "meeting", "report",
        "colleague", "team", "customer", "customer", "collaborate", "collaborate", "collaborate"
    ]
    
    for term in work_terms:
        if term in subject:
            print(f"[INFO] Work keyword match (subject): '{term}' -> Work")
            return "Work"
        if term in body_lower[:300]:
            print(f"[INFO] Work keyword match (body): '{term}' -> Work")
            return "Work"
    
    # Personal category keywords
    personal_terms = [
        "personal", "friend", "family", "social", "invite", "invitation",
        "party", "celebration", "birthday", "wedding", "travel", "trip",
        "private", "personal", "friend", "family", "social", "invite", "party", "celebration",
        "birthday", "travel", "tour", "private", "vacation", "holiday"
    ]
    
    for term in personal_terms:
        if term in subject:
            print(f"[INFO] Personal keyword match (subject): '{term}' -> Personal")
            return "Personal"
        if term in body_lower[:300]:
            print(f"[INFO] Personal keyword match (body): '{term}' -> Personal")
            return "Personal"
    
    # Update category keywords
    update_terms = [
        "update", "upgrade", "new version", "update", "patch", "version", "release",
        "improvement", "enhancement", "system", "software", "app", "application",
        "changelog", "change log", "new feature", "feature", "improvement"
    ]
    
    for term in update_terms:
        if term in subject:
            print(f"[INFO] Update keyword match (subject): '{term}' -> Update")
            return "Update"
        if term in body_lower[:300]:
            print(f"[INFO] Update keyword match (body): '{term}' -> Update")
            return "Update"
    
    # Transaction category keywords
    transaction_terms = [
        "transaction", "receipt", "payment", "order", "purchase", "transaction", "payment",
        "order", "payment", "bill", "invoice", "statement", "purchase", "bought",
        "paid", "confirmation", "shipped", "delivery", "tracking", "bill"
    ]
    
    for term in transaction_terms:
        if term in subject:
            print(f"[INFO] Transaction keyword match (subject): '{term}' -> Transaction")
            return "Transaction"
        if term in body_lower[:300]:
            print(f"[INFO] Transaction keyword match (body): '{term}' -> Transaction")
            return "Transaction"
    
    # Promotion category keywords (check when other rules don't match)
    promotion_terms = [
        "promotion", "discount", "sale", "offer", "deal", "coupon", "code",
        "subscription", "newsletter", "marketing", "advertisement", "promotion", "discount",
        "discount", "special price", "limited time", "flash sale", "full reduction", "new product", "activity", "special"
    ]
    
    for term in promotion_terms:
        if term in subject:
            print(f"[INFO] Promotion keyword match (subject): '{term}' -> Promotion")
            return "Promotion"
        if term in from_addr:
            print(f"[INFO] Promotion keyword match (sender): '{term}' -> Promotion")
            return "Promotion"
        if term in body_lower[:500]:
            print(f"[INFO] Promotion keyword match (body): '{term}' -> Promotion")
            return "Promotion"
    
    # No rule matched, return default category
    print(f"[INFO] No rule matched. Defaulting to LowPriority.")
    return "LowPriority"

def classify_content(body: str, headers: dict) -> str:
    """
    Entry: directly return the result of classify_main (one of the eight categories)
    """
    return classify_main(body, headers)

def fetch_plaintext(msg) -> str:
    """
    Extract pure text content from email.message.Message:
    - Prefer to return text/plain part
    - If not, decode the entire payload
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return (part.get_payload(decode=True) or b"").decode(errors="ignore")
    return (msg.get_payload(decode=True) or b"").decode(errors="ignore")
