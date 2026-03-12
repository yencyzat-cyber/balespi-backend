from fastapi import FastAPI
from supabase import create_client, Client
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid

SUPABASE_URL = "https://erwhreatpqxnxcirkozx.supabase.co"
SUPABASE_KEY = "sb_publishable_N0Jl61BZYHq-HTIAdFeDXw_3Ku-M3lY"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI(title="Balespi Import API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
def leer_raiz():
    return {"mensaje": "¡Balespi API PRO 100% activa!"}

@app.get("/productos")
def obtener_productos():
    respuesta = supabase.table("products").select("*").order("name").execute()
    return respuesta.data

@app.get("/pedidos")
def obtener_pedidos():
    respuesta = supabase.table("orders").select("*").order("created_at", desc=True).execute()
    return respuesta.data

@app.post("/registrar_venta")
def registrar_venta(venta: Venta):
    try:
        supabase.table("orders").insert({
            "id": venta.order_id,
            "seller": venta.seller,
            "client": venta.client,
            "phone": venta.phone,
            "channel": venta.channel,
            "status": "verificado" if venta.channel == "tienda" else "pago_pendiente",
            "subtotal": venta.subtotal,
            "discount": venta.discount_pct,
            "total": venta.total,
            "notes": venta.notes,
            "internal_note": venta.internal_note,
            "items": [item.dict() for item in venta.items]
        }).execute()

        for item in venta.items:
            prod = supabase.table("products").select("*").eq("id", item.product_id).execute().data[0]
            col = f"stock_{venta.channel}"
            
            unidades = item.qty
            if item.sale_type == "docena":
                unidades = item.qty * prod.get("per_dozen", 12)
            elif item.sale_type == "cajon":
                unidades = item.qty * prod.get("per_box", 20)
                
            nuevo_stock = prod[col] - unidades
            supabase.table("products").update({col: nuevo_stock}).eq("id", item.product_id).execute()
        
        return {"estado": "exito", "order_id": venta.order_id}
    except Exception as e:
        return {"estado": "error", "detalle": str(e)}

@app.post("/crear_producto")
def crear_producto(p: dict):
    try:
        # Detecta si es un producto nuevo o una edición
        is_new = str(p.get("id")).isnumeric() or p.get("id") is None
        prod_id = str(uuid.uuid4()) if is_new else str(p.get("id"))

        db_prod = {
            "id": prod_id,
            "name": p.get("name"),
            "sku": p.get("sku"),
            "cat": p.get("cat", "General"),
            "icon": p.get("icon", "📦"),
            "photo_url": p.get("photo"),
            "price_tienda": p.get("prices", {}).get("tienda", 0),
            "price_live": p.get("prices", {}).get("live", 0),
            "price_docena": p.get("prices", {}).get("docena_unit", 0),
            "price_cajon": p.get("prices", {}).get("cajon_unit", 0),
            "stock_tienda": p.get("stockTienda", 0),
            "stock_live": p.get("stockLive", 0),
            "stock_min": p.get("stockMin", 5),
            "per_dozen": p.get("perDozen", 12),
            "per_box": p.get("perBox", 20),
            "promo_pct": p.get("promo", {}).get("pct", 0) if p.get("promo") else 0,
            "active": p.get("active", True)
        }
        supabase.table("products").upsert(db_prod).execute()
        return {"estado": "exito", "id": prod_id}
    except Exception as e:
        return {"estado": "error", "detalle": str(e)}

@app.post("/actualizar_stock")
def actualizar_stock(data: dict):
    try:
        supabase.table("products").update({
            "stock_tienda": data.get("stock_tienda"),
            "stock_live": data.get("stock_live")
        }).eq("id", data.get("id")).execute()
        return {"estado": "exito"}
    except Exception as e:
        return {"estado": "error", "detalle": str(e)}
