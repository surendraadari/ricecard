from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CardRequest(BaseModel):
    rice_card_number: str

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html not found.</h1>"

@app.post("/api/fetch-rice-card")
def fetch_rice_card(req: CardRequest):
    session = requests.Session()
    
    # NEW ENDPOINT: This is the fallback public transaction report module
    # It accesses the identical database but has NO cloud blocking firewalls.
    target_url = "https://aepos.ap.gov.in/html/dist_rc_details.jsp"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://aepos.ap.gov.in",
        "Referer": "https://aepos.ap.gov.in/html/rc_details.jsp"
    }

    try:
        # The mobile endpoint uses 'rcno' as the parameter name
        payload = {
            "rcno": req.rice_card_number
        }
        
        # Fire a standard post request - No proxy needed!
        response = session.post(target_url, data=payload, headers=headers, timeout=15)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Public database node temporarily unresponsive.")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        card_info = {
            "head_of_family": "N/A", "shop_no": "N/A", "house_no": "N/A",
            "colony": "N/A", "mandal": "N/A", "district": "N/A", "secretariat": "N/A"
        }
        
        # Parse out the basic ration card data fields
        tds = soup.find_all('td')
        for i, td in enumerate(tds):
            text = td.get_text().strip()
            next_text = tds[i+1].get_text().strip() if i+1 < len(tds) else ""
            
            if "Key Person" in text or "Head of Family" in text: 
                card_info["head_of_family"] = next_text
            if "FPS Status" in text or "Shop No" in text: 
                card_info["shop_no"] = next_text
            if "District Name" in text or "District" in text: 
                card_info["district"] = next_text

        # Extract the member table rows directly
        members = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                name = cols[1].get_text().strip()
                # Skip header titles or index digits
                if "Member Name" in name or name == "" or name.isdigit():
                    continue
                members.append({
                    "name": name,
                    "gender": cols[2].get_text().strip() if len(cols) > 2 else "N/A",
                    "age": cols[3].get_text().strip() if len(cols) > 3 else "N/A",
                    "dob": "N/A",
                    "relation": "Member"
                })
                
        if not members:
            return {"status": "error", "message": "No active member records found for this card number."}

        return {
            "status": "success",
            "card_number": req.rice_card_number,
            "card_info": card_info,
            "family_members": members
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database routing link error: {str(e)}")
