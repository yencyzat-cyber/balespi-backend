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

class UpdatePedido(BaseModel):
    id: str
    status: Optional[str] = None
    internal_note: Optional[str] = None

@app.get("/")
def leer_raiz(): return {"mensaje": "API Activa"}

@app.get("/productos")
def obtener_productos(): return supabase.table("products").select("*").order("name").execute().data

@app.get("/pedidos")
def obtener_pedidos(): return supabase.table("orders").select("*").order("created_at", desc=True).execute().data

@app.get("/traspasos")
def obtener_traspasos(): return supabase.table("stock_transfers").select("*").order("created_at", desc=True).execute().data

@app.get("/clientes")
def obtener_clientes(): return supabase.table("clients").select("*").execute().data

@app.post("/registrar_venta")
def registrar_venta(venta: Venta):
    try:
        status_inicial = "entregado" if venta.channel == "tienda" else "pago_pendiente"
        
        supabase.table("orders").insert({
            "id": venta.order_id, "seller": venta.seller, "client": venta.client, "phone": venta.phone,
            "channel": venta.channel, "status": status_inicial, "subtotal": venta.subtotal,
            "discount": venta.discount_pct, "total": venta.total, "notes": venta.notes,
            "internal_note": venta.internal_note, "items": [i.dict() for i in venta.items]
        }).execute()

        # Guardar / Actualizar Cliente Automáticamente
        if venta.channel == "live" and venta.phone:
            supabase.table("clients").upsert({
                "phone": venta.phone, "name": venta.client, "address": venta.notes
            }).execute()

        # Descontar stock y generar traspasos oficiales si falta
        for item in venta.items:
            prod = supabase.table("products").select("*").eq("id", item.product_id).execute().data[0]
            col = f"stock_{venta.channel}"
            other_col = "stock_tienda" if venta.channel == "live" else "stock_live"
            
            unidades = item.qty
            if item.sale_type == "docena": unidades *= prod.get("per_dozen", 12)
            elif item.sale_type == "cajon": unidades *= prod.get("per_box", 20)
                
            avail = prod[col]
            if avail < unidades:
                # Faltan unidades -> Crear Traspaso Oficial
                falta = unidades - avail
                supabase.table("stock_transfers").insert({
                    "id": f"TRF-{uuid.uuid4().hex[:6].upper()}",
                    "pid": prod["id"], "product_name": prod["name"], "product_icon": prod["icon"],
                    "unidades": falta, "de_channel": "live" if venta.channel == "tienda" else "tienda",
                    "de_key": other_col, "a_channel": venta.channel, "order_id": venta.order_id
                }).execute()
            
            supabase.table("products").update({col: avail - unidades}).eq("id", item.product_id).execute()
        
        return {"estado": "exito", "order_id": venta.order_id}
    except Exception as e: return {"estado": "error", "detalle": str(e)}

@app.post("/crear_producto")
def crear_producto(p: dict):
    try:
        is_new = str(p.get("id")).isnumeric() or p.get("id") is None
        prod_id = str(uuid.uuid4()) if is_new else str(p.get("id"))
        db_prod = {
            "id": prod_id, "name": p.get("name"), "sku": p.get("sku"), "cat": p.get("cat", "General"),
            "icon": p.get("icon", "📦"), "photo_url": p.get("photo"),
            "price_tienda": p.get("prices", {}).get("tienda", 0), "price_live": p.get("prices", {}).get("live", 0),
            "price_docena": p.get("prices", {}).get("docena_unit", 0), "price_cajon": p.get("prices", {}).get("cajon_unit", 0),
            "stock_tienda": p.get("stockTienda", 0), "stock_live": p.get("stockLive", 0),
            "stock_min": p.get("stockMin", 5), "per_dozen": p.get("perDozen", 12), "per_box": p.get("perBox", 20),
            "promo_pct": p.get("promo", {}).get("pct", 0) if p.get("promo") else 0, "active": p.get("active", True)
        }
        supabase.table("products").upsert(db_prod).execute()
        return {"estado": "exito", "id": prod_id}
    except Exception as e: return {"estado": "error", "detalle": str(e)}

@app.post("/actualizar_stock")
def actualizar_stock(data: dict):
    try:
        supabase.table("products").update({"stock_tienda": data.get("stock_tienda"), "stock_live": data.get("stock_live")}).eq("id", data.get("id")).execute()
        return {"estado": "exito"}
    except Exception as e: return {"estado": "error", "detalle": str(e)}

@app.post("/actualizar_pedido")
def actualizar_pedido(data: UpdatePedido):
    try:
        upd = {}
        if data.status: upd["status"] = data.status
        if data.internal_note is not None: upd["internal_note"] = data.internal_note
        supabase.table("orders").update(upd).eq("id", data.id).execute()
        return {"estado": "exito"}
    except Exception as e: return {"estado": "error"}

@app.post("/actualizar_traspaso")
def actualizar_traspaso(data: dict):
    try:
        supabase.table("stock_transfers").update({"status": data["status"], "confirmed_by": data.get("role")}).eq("id", data["id"]).execute()
        if data["status"] == "confirmado":
            t = supabase.table("stock_transfers").select("*").eq("id", data["id"]).execute().data[0]
            p = supabase.table("products").select("*").eq("id", t["pid"]).execute().data[0]
            supabase.table("products").update({t["de_key"]: p[t["de_key"]] - t["unidades"]}).eq("id", t["pid"]).execute()
        return {"estado": "exito"}
    except Exception as e: return {"estado": "error"}
