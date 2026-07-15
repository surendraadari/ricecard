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
    
    # SHIFT PORTAL TARGET: Using alternate domain destination parameters
    # to pull raw data index feeds from unblocked frameworks.
    search_url = "https://aepos.ap.gov.in/html/dist_rc_details.jsp"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://aepos.ap.gov.in",
        "Referer": "https://aepos.ap.gov.in/html/rc_details.jsp"
    }

    try:
        # Pass payload parameters direct to public index feed
        payload = {
            "rcno": req.rice_card_number
        }
        
        response = session.post(search_url, data=payload, headers=headers, timeout=20)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Alternate server unreachable: Status {response.status_code}")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        card_info = {
            "head_of_family": "N/A", "shop_no": "N/A", "house_no": "N/A",
            "colony": "N/A", "mandal": "N/A", "district": "N/A", "secretariat": "N/A"
        }
        
        # Parse alternate table text layout maps
        tds = soup.find_all('td')
        for i, td in enumerate(tds):
            text = td.get_text().strip()
            next_text = tds[i+1].get_text().strip() if i+1 < len(tds) else ""
            
            if "Key Person" in text: card_info["head_of_family"] = next_text
            if "FPS Status" in text or "Shop No" in text: card_info["shop_no"] = next_text
            if "District" in text: card_info["district"] = next_text

        members = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            # Balance alternate layout schema table indexes
            if len(cols) >= 4:
                name = cols[1].get_text().strip()
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
            return {"status": "error", "message": "No matching record found on the fallback routing directory."}

        return {
            "status": "success",
            "card_number": req.rice_card_number,
            "card_info": card_info,
            "family_members": members
        }

    except Exception as e:
        import traceback
        print("--- ALTRNATE ROUTE ERROR ---")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fallback portal connection failure: {str(e)}")
