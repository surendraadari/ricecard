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
    search_url = "https://epds.ap.gov.in/epdsAP/epds/Ricecard_Search_Screen_latest.epds"
    
    # Updated proxies dictionary with your working free list details
    proxies = {
        "http": "http://ukeshdlr:uglumxvbza5h@38.154.185.97:6370/",
        "https": "http://ukeshdlr:uglumxvbza5h@38.154.185.97:6370/"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://epds.ap.gov.in",
        "Referer": "https://epds.ap.gov.in/epdsAP/epds/publicepdsDashBoard.epds"
    }

    try:
        payload = {
            "csrfPreventionSalt": "",
            "rice_card_no": req.rice_card_number
        }
        
        response = session.post(search_url, data=payload, headers=headers, proxies=proxies, timeout=25)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Target portal rejected connection with status: {response.status_code}")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        card_info = {
            "head_of_family": "N/A", "shop_no": "N/A", "house_no": "N/A",
            "colony": "N/A", "mandal": "N/A", "district": "N/A", "secretariat": "N/A"
        }
        
        tds = soup.find_all(['td', 'th', 'span'])
        for i, td in enumerate(tds):
            text = td.get_text().strip()
            next_text = tds[i+1].get_text().strip() if i+1 < len(tds) else ""
            
            if "Name of Head Of Family" in text:
                card_info["head_of_family"] = text.split(":")[-1].strip() if ":" in text else next_text
            if "Shop No" in text: card_info["shop_no"] = next_text
            if "House No" in text: card_info["house_no"] = next_text
            if "Colony" in text: card_info["colony"] = next_text
            if "Mandal" in text: card_info["mandal"] = next_text
            if "District" in text: card_info["district"] = next_text
            if "Secretariat Name" in text: card_info["secretariat"] = next_text

        members = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                name = cols[0].get_text().strip()
                if "Name" in name or name == "" or name.isdigit():
                    continue
                members.append({
                    "name": name,
                    "gender": cols[1].get_text().strip() if len(cols) > 1 else "N/A",
                    "age": cols[2].get_text().strip() if len(cols) > 2 else "N/A",
                    "dob": cols[3].get_text().strip() if len(cols) > 3 else "N/A",
                    "relation": cols[4].get_text().strip() if len(cols) > 4 else "N/A"
                })
                
        if not members and "No Details Found" in response.text:
            return {"status": "error", "message": "No matching active record found for index sequence."}

        return {
            "status": "success",
            "card_number": req.rice_card_number,
            "card_info": card_info,
            "family_members": members
        }

    except Exception as e:
        import traceback
        print("--- PROXY SCRAPING EXECUTION FAIL ---")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Data parser processing layout failure: {str(e)}")
