from fastapi import FastAPI
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid

# 1. Credenciales de Balespi Import
SUPABASE_URL = "https://erwhreatpqxnxcirkozx.supabase.co"
SUPABASE_KEY = "sb_publishable_N0Jl61BZYHq-HTIAdFeDXw_3Ku-M3lY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Inicializamos la API
app = FastAPI(title="Balespi Import API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class ItemVenta(BaseModel):
    product_id: str
    sale_type: str 
    qty: int
    price_applied: float

class Venta(BaseModel):
    order_id: str
    seller: str
    client: str
    phone: Optional[str] = ""
    channel: str 
    subtotal: float
    discount_pct: int = 0
    total: float
    notes: Optional[str] = ""
    internal_note: Optional[str] = ""
    items: List[ItemVenta]

# 3. Endpoints
@app.get("/")
def leer_raiz():
    return {"mensaje": "¡Balespi API 24/7 activa!"}

@app.get("/productos")
def obtener_productos():
    respuesta = supabase.table("products").select("*").execute()
    return respuesta.data

@app.post("/registrar_venta")
def registrar_venta(venta: Venta):
    # Registrar cabecera
    supabase.table("orders").insert({
        "id": venta.order_id,
        "seller": venta.seller,
        "client": venta.client,
        "phone": venta.phone,
        "channel": venta.channel,
        "total": venta.total
    }).execute()

    for item in venta.items:
        # Lógica de stock simplificada para la nube
        prod = supabase.table("products").select("*").eq("id", item.product_id).execute().data[0]
        col = f"stock_{venta.channel}"
        nuevo_stock = prod[col] - item.qty
        supabase.table("products").update({col: nuevo_stock}).eq("id", item.product_id).execute()
    
    return {"estado": "exito", "order_id": venta.order_id}
