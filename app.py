import streamlit as st
import requests
from lxml import etree
from io import BytesIO
from datetime import date

# --- Config ---
SHOP = "superduper-hats.myshopify.com"
API_VERSION = "2023-10"
ACCESS_TOKEN = st.secrets["SHOPIFY_TOKEN"]
BASE_URL = f"https://{SHOP}/admin/api/{API_VERSION}"
HEADERS = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json"
}

# --- Funzioni ---
def get_order_by_name(order_number):
    order_name = f"#{order_number}"
    url = f"{BASE_URL}/orders.json?name={order_name}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        orders = res.json().get('orders', [])
        return orders[0] if orders else None
    return None

def build_invoice_xml(order, protocol_number, invoice_date):
    nsmap = {None: "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}
    root = etree.Element("FatturaElettronica", nsmap=nsmap, versione="FPR12")

    # Header
    header = etree.SubElement(root, "FatturaElettronicaHeader")
    cedente = etree.SubElement(header, "CedentePrestatore")
    dati_anagrafici = etree.SubElement(cedente, "DatiAnagrafici")
    id_fiscale = etree.SubElement(dati_anagrafici, "IdFiscaleIVA")
    etree.SubElement(id_fiscale, "IdPaese").text = "IT"
    etree.SubElement(id_fiscale, "IdCodice").text = "01087530521"
    etree.SubElement(dati_anagrafici, "CodiceFiscale").text = "01087530521"
    denominazione = etree.SubElement(etree.SubElement(dati_anagrafici, "Anagrafica"), "Denominazione")
    denominazione.text = "SUPERDUPER S.R.L."

    # Cliente
    cessionario = etree.SubElement(header, "CessionarioCommittente")
    dati_cliente = etree.SubElement(cessionario, "DatiAnagrafici")
    etree.SubElement(dati_cliente, "CodiceFiscale").text = "KLSDNL92"  # placeholder
    anagrafica_cliente = etree.SubElement(dati_cliente, "Anagrafica")
    etree.SubElement(anagrafica_cliente, "Nome").text = order["billing_address"]["first_name"]
    etree.SubElement(anagrafica_cliente, "Cognome").text = order["billing_address"]["last_name"]
    indirizzo_cliente = etree.SubElement(cessionario, "Sede")
    etree.SubElement(indirizzo_cliente, "Indirizzo").text = order["billing_address"]["address1"]
    etree.SubElement(indirizzo_cliente, "CAP").text = order["billing_address"]["zip"]
    etree.SubElement(indirizzo_cliente, "Comune").text = order["billing_address"]["city"]
    etree.SubElement(indirizzo_cliente, "Provincia").text = order["billing_address"]["province_code"]
    etree.SubElement(indirizzo_cliente, "Nazione").text = order["billing_address"]["country_code"]

    # Body
    body = etree.SubElement(root, "FatturaElettronicaBody")
    dati_generali = etree.SubElement(body, "DatiGenerali")
    dati_generali_doc = etree.SubElement(dati_generali, "DatiGeneraliDocumento")
    etree.SubElement(dati_generali_doc, "TipoDocumento").text = "TD01"
    etree.SubElement(dati_generali_doc, "Divisa").text = "EUR"
    etree.SubElement(dati_generali_doc, "Data").text = invoice_date.strftime("%Y-%m-%d")
    etree.SubElement(dati_generali_doc, "Numero").text = str(protocol_number)
    etree.SubElement(dati_generali_doc, "ImportoTotaleDocumento").text = order["total_price"]

    # Linee ordine
    dettagli = etree.SubElement(body, "DatiBeniServizi")
    for idx, item in enumerate(order["line_items"], start=1):
        linea = etree.SubElement(dettagli, "DettaglioLinee")
        etree.SubElement(linea, "NumeroLinea").text = str(idx)
        etree.SubElement(linea, "Descrizione").text = item["title"]
        etree.SubElement(linea, "Quantita").text = str(item["quantity"])
        etree.SubElement(linea, "PrezzoUnitario").text = item["price"]
        etree.SubElement(linea, "PrezzoTotale").text = item["price"]
        etree.SubElement(linea, "AliquotaIVA").text = "22.00"

    # Riepilogo
    riepilogo = etree.SubElement(dettagli, "DatiRiepilogo")
    etree.SubElement(riepilogo, "AliquotaIVA").text = "22.00"
    etree.SubElement(riepilogo, "ImponibileImporto").text = order["subtotal_price"]
    etree.SubElement(riepilogo, "Imposta").text = "0.00"
    etree.SubElement(riepilogo, "EsigibilitaIVA").text = "I"

    xml_bytes = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    return xml_bytes

# --- UI Streamlit ---
st.title("💾 Generatore Fattura XML da Shopify")
order_input = st.text_input("📦 Numero ordine Shopify (es: #5552)", value="#")
protocol_input = st.text_input("📁 Numero di protocollo")
date_input = st.date_input("🗓️ Data di emissione", value=date.today())

if st.button("Genera XML"):
    order_number = order_input.strip().lstrip("#")
    order = get_order_by_name(order_number)
    if order:
        xml_data = build_invoice_xml(order, protocol_input, date_input)
        file_name = f"fattura_{order_number}.xml"
        st.success("✅ Fattura generata con successo!")
        st.download_button("📅 Scarica XML", data=xml_data, file_name=file_name, mime="application/xml")
    else:
        st.error("❌ Ordine non trovato.")
