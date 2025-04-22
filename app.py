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
    nsmap = {
        None: "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    }
    root = etree.Element("p:FatturaElettronica", nsmap=nsmap, attrib={"versione": "FPR12"})

    # HEADER
    header = etree.SubElement(root, "FatturaElettronicaHeader")

    trasmissione = etree.SubElement(header, "DatiTrasmissione")
    id_trasmittente = etree.SubElement(trasmissione, "IdTrasmittente")
    etree.SubElement(id_trasmittente, "IdPaese").text = "IT"
    etree.SubElement(id_trasmittente, "IdCodice").text = "01087530521"
    etree.SubElement(trasmissione, "ProgressivoInvio").text = str(protocol_number)
    etree.SubElement(trasmissione, "FormatoTrasmissione").text = "FPR12"
    etree.SubElement(trasmissione, "CodiceDestinatario").text = "0000000"

    cedente = etree.SubElement(header, "CedentePrestatore")
    dati_anagrafici = etree.SubElement(cedente, "DatiAnagrafici")
    id_fiscale = etree.SubElement(dati_anagrafici, "IdFiscaleIVA")
    etree.SubElement(id_fiscale, "IdPaese").text = "IT"
    etree.SubElement(id_fiscale, "IdCodice").text = "01087530521"
    etree.SubElement(dati_anagrafici, "CodiceFiscale").text = "01087530521"
    anagrafica = etree.SubElement(dati_anagrafici, "Anagrafica")
    etree.SubElement(anagrafica, "Denominazione").text = "SUPERDUPER S.R.L."
    etree.SubElement(dati_anagrafici, "RegimeFiscale").text = "RF19"

    sede = etree.SubElement(cedente, "Sede")
    etree.SubElement(sede, "Indirizzo").text = "VIA DI CITTADELLA 39R"
    etree.SubElement(sede, "CAP").text = "50144"
    etree.SubElement(sede, "Comune").text = "FIRENZE"
    etree.SubElement(sede, "Provincia").text = "FI"
    etree.SubElement(sede, "Nazione").text = "IT"

    cliente = etree.SubElement(header, "CessionarioCommittente")
    dati_cliente = etree.SubElement(cliente, "DatiAnagrafici")
    anagrafica_cliente = etree.SubElement(dati_cliente, "Anagrafica")
    etree.SubElement(anagrafica_cliente, "Nome").text = order["billing_address"]["first_name"]
    etree.SubElement(anagrafica_cliente, "Cognome").text = order["billing_address"]["last_name"]
    sede_cliente = etree.SubElement(cliente, "Sede")
    etree.SubElement(sede_cliente, "Indirizzo").text = order["billing_address"]["address1"]
    etree.SubElement(sede_cliente, "CAP").text = order["billing_address"]["zip"]
    etree.SubElement(sede_cliente, "Comune").text = order["billing_address"]["city"]
    etree.SubElement(sede_cliente, "Provincia").text = order["billing_address"]["province_code"]
    etree.SubElement(sede_cliente, "Nazione").text = order["billing_address"]["country_code"]

    # BODY
    body = etree.SubElement(root, "FatturaElettronicaBody")
    dati_generali = etree.SubElement(body, "DatiGenerali")
    dati_documento = etree.SubElement(dati_generali, "DatiGeneraliDocumento")
    etree.SubElement(dati_documento, "TipoDocumento").text = "TD01"
    etree.SubElement(dati_documento, "Divisa").text = "EUR"
    etree.SubElement(dati_documento, "Data").text = invoice_date.strftime("%Y-%m-%d")
    etree.SubElement(dati_documento, "Numero").text = str(protocol_number)
    etree.SubElement(dati_documento, "ImportoTotaleDocumento").text = order["total_price"]
    etree.SubElement(dati_documento, "Causale").text = f"Vendita ordine Shopify {order['name']}"

    dettagli = etree.SubElement(body, "DatiBeniServizi")
    for idx, item in enumerate(order["line_items"], start=1):
        linea = etree.SubElement(dettagli, "DettaglioLinee")
        etree.SubElement(linea, "NumeroLinea").text = str(idx)
        etree.SubElement(linea, "Descrizione").text = item["title"]
        etree.SubElement(linea, "Quantita").text = str(item["quantity"])
        etree.SubElement(linea, "UnitaMisura").text = "pz"
        etree.SubElement(linea, "PrezzoUnitario").text = item["price"]
        etree.SubElement(linea, "PrezzoTotale").text = item["price"]
        etree.SubElement(linea, "AliquotaIVA").text = "22.00"

    riepilogo = etree.SubElement(dettagli, "DatiRiepilogo")
    etree.SubElement(riepilogo, "AliquotaIVA").text = "22.00"
    etree.SubElement(riepilogo, "ImponibileImporto").text = order["subtotal_price"]
    etree.SubElement(riepilogo, "Imposta").text = "0.00"
    etree.SubElement(riepilogo, "EsigibilitaIVA").text = "I"

    xml_bytes = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    return xml_bytes

# --- UI Streamlit ---
st.title("🧾 Generatore Fattura XML da Shopify")
order_input = st.text_input("📦 Numero ordine Shopify (es: #5552)", value="#")
protocol_input = st.text_input("📑 Numero di protocollo")
date_input = st.date_input("🗓️ Data di emissione", value=date.today())

if st.button("Genera XML"):
    order_number = order_input.strip().lstrip("#")
    order = get_order_by_name(order_number)
    if order:
        xml_data = build_invoice_xml(order, protocol_input, date_input)
        file_name = f"fattura_{order_number}.xml"
        st.success("✅ Fattura generata con successo!")
        st.download_button("📥 Scarica XML", data=xml_data, file_name=file_name, mime="application/xml")
    else:
        st.error("❌ Ordine non trovato.")
