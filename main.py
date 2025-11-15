import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Pet, Adoptionrequest, User

app = FastAPI(title="Paws & Hugs - Pet Adoption API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Paws & Hugs API"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Utilities
class PetOut(BaseModel):
    id: str
    name: str
    species: str
    age_years: float
    gender: str
    size: str
    description: Optional[str] = None
    photo_url: Optional[str] = None
    location: Optional[str] = None
    is_adopted: bool

    @staticmethod
    def from_mongo(doc: dict) -> "PetOut":
        return PetOut(
            id=str(doc.get("_id")),
            name=doc.get("name"),
            species=doc.get("species"),
            age_years=doc.get("age_years"),
            gender=doc.get("gender"),
            size=doc.get("size"),
            description=doc.get("description"),
            photo_url=doc.get("photo_url"),
            location=doc.get("location"),
            is_adopted=doc.get("is_adopted", False),
        )

# Seed sample pets if collection empty
@app.post("/seed", tags=["dev"])
def seed_pets():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    count = db["pet"].count_documents({})
    if count > 0:
        return {"message": "Already seeded", "count": count}

    sample_pets = [
        {
            "name": "Mocha",
            "species": "Dog",
            "age_years": 1.5,
            "gender": "Female",
            "size": "Small",
            "description": "Sweet, snuggly pup who loves belly rubs.",
            "photo_url": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=900&q=80&auto=format&fit=crop",
            "location": "Sunnyvale Shelter",
            "is_adopted": False,
        },
        {
            "name": "Miso",
            "species": "Cat",
            "age_years": 3,
            "gender": "Male",
            "size": "Small",
            "description": "Calm lap cat, purr motor included.",
            "photo_url": "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?w=900&q=80&auto=format&fit=crop",
            "location": "Palo Alto Rescue",
            "is_adopted": False,
        },
        {
            "name": "Taro",
            "species": "Rabbit",
            "age_years": 2,
            "gender": "Female",
            "size": "Small",
            "description": "Gentle bun who loves leafy greens.",
            "photo_url": "https://images.unsplash.com/photo-1548767797-d8c844163c4c?w=900&q=80&auto=format&fit=crop",
            "location": "Mountain View Haven",
            "is_adopted": False,
        },
    ]
    for p in sample_pets:
        create_document("pet", p)
    return {"message": "Seeded", "count": len(sample_pets)}

# API Endpoints
@app.get("/api/pets", response_model=List[PetOut])
def list_pets(species: Optional[str] = None, size: Optional[str] = None, q: Optional[str] = None):
    filter_q = {"is_adopted": False}
    if species:
        filter_q["species"] = species
    if size:
        filter_q["size"] = size
    if q:
        filter_q["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"location": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("pet", filter_q)
    return [PetOut.from_mongo(d) for d in docs]

@app.post("/api/adopt")
def create_adoption_request(req: Adoptionrequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    # Validate pet exists
    try:
        oid = ObjectId(req.pet_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid pet ID")

    pet = db["pet"].find_one({"_id": oid})
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    req_id = create_document("adoptionrequest", req)
    return {"message": "Request received", "request_id": req_id}

@app.get("/schema")
def get_schema_info():
    # Minimal endpoint so studio can introspect schemas
    from schemas import __dict__ as schema_dict
    # Only return Pydantic model names
    models = [name for name, obj in schema_dict.items() if getattr(obj, "__base__", None) is BaseModel.__base__]
    return {"models": models}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
