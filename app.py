import streamlit as st
import sqlite3
import pandas as pd
import cv2
import os
import qrcode
from io import BytesIO

# ==========================================
# 1. DATABASE RESTRUCTURE & FILE STORAGE SETUP
# ==========================================
conn = sqlite3.connect("inventory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS wheelchairs (
        serial_number TEXT PRIMARY KEY,
        model_type TEXT,
        status TEXT,
        installed_battery_serial TEXT,
        dispatch_date TEXT,
        customer_name TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS batteries (
        serial_number TEXT PRIMARY KEY,
        capacity_batch TEXT,
        status TEXT,
        assigned_wheelchair_serial TEXT
    )
""")
conn.commit()

# Create a permanent folder on your laptop to store the QR image files
QR_FOLDER = "generated_qrs"
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

def generate_next_serials(prefix, count):
    table = "wheelchairs" if prefix == "WC" else "batteries"
    cursor.execute(f"SELECT serial_number FROM {table} WHERE serial_number LIKE '{prefix}-2026-%' ORDER BY serial_number DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        last_serial = row[0]
        last_num = int(last_serial.split("-")[-1])
    else:
        last_num = 0
    new_serials = []
    for i in range(1, count + 1):
        next_num = last_num + i
        new_serials.append(f"{prefix}-2026-{next_num:06d}")
    return new_serials

# ==========================================
# 2. APP LAYOUT AND CONFIGURATION
# ==========================================
st.set_page_config(page_title="Medical Device Serialization Hub", layout="wide")

st.markdown("""
    <style>
    .kpi-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #007bff;
        margin-bottom: 15px;
    }
    .kpi-card.battery { border-left-color: #28a745; }
    .kpi-card.alert { border-left-color: #ffc107; }
    .kpi-title { font-size: 13px; color: #6c757d; font-weight: bold; text-transform: uppercase; }
    .kpi-value { font-size: 26px; font-weight: bold; color: #212529; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)


col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists("company_logo.jpeg"):
        st.image("company_logo.jpeg", width=130)
    else:
        st.subheader("🏢")
        
with col_title:
    st.title("Pulse Device Traceability & Serialization Hub")

# This creates a full-width centered block for your subtitle
st.markdown(
    "<p style='text-align: center; color: #6c757d; font-size: 15px; margin-top: -10px;'>"
    "India to World • Precision Medical Device Ledger • Device Birth Records"
    "</p>", 
    unsafe_allow_html=True
)

st.markdown("---")

tab_overview, tab_generator, tab_assembly, tab_dispatch = st.tabs([
    "📊 Global Inventory Registry", 
    "🖨️ Batch QR Serial Generator", 
    "🔧 Production Floor (Assemble)", 
    "🚚 Logistics Hub (Dispatch Orders)"
])

# ==========================================
# TAB 1: GLOBAL INVENTORY REGISTRY
# ==========================================
with tab_overview:
    wc_total = cursor.execute("SELECT COUNT(*) FROM wheelchairs").fetchone()[0]
    wc_ready = cursor.execute("SELECT COUNT(*) FROM wheelchairs WHERE status='Ready for Battery'").fetchone()[0]
    bat_avail = cursor.execute("SELECT COUNT(*) FROM batteries WHERE status='In Stock (Available)'").fetchone()[0]
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">♿ Total Manufactured Wheelchairs</div><div class="kpi-value">{wc_total} Units</div></div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown(f'<div class="kpi-card alert"><div class="kpi-title">⏳ Frames Waiting for Battery</div><div class="kpi-value">{wc_ready} Units</div></div>', unsafe_allow_html=True)
    with m_col3:
        st.markdown(f'<div class="kpi-card battery"><div class="kpi-title">🔋 Loose Batteries In Stock</div><div class="kpi-value">{bat_avail} Packs</div></div>', unsafe_allow_html=True)
        
    st.markdown("### 📋 Wheelchair Master Ledger")
    df_wc = pd.read_sql_query("SELECT serial_number as 'Serial Number', model_type as 'Model Specification', status as 'Production Status', installed_battery_serial as 'Linked Battery SN', customer_name as 'Assigned Customer', dispatch_date as 'Shipment Date' FROM wheelchairs", conn)
    st.dataframe(df_wc, width='stretch', hide_index=True)
    
    st.markdown("### 📋 Battery Master Ledger")
    df_bat = pd.read_sql_query("SELECT serial_number as 'Serial Number', capacity_batch as 'Batch Details', status as 'Status Profile', assigned_wheelchair_serial as 'Parent Device SN' FROM batteries", conn)
    st.dataframe(df_bat, width='stretch', hide_index=True)

# ==========================================
# TAB 2: BATCH QR SERIAL GENERATOR (UPDATED TO SAVE FILES)
# ==========================================
with tab_generator:
    st.subheader("Generate Unique Identity Matrix Profiles")
    gen_col1, gen_col2 = st.columns(2)
    with gen_col1:
        device_type = st.selectbox("Equipment Category Line", ["Wheelchair (WC)", "Battery Pack (BAT)"])
        batch_size = st.number_input("Manufactured Run Quantity count", min_value=1, max_value=50, value=3, step=1)
        
        if device_type == "Wheelchair (WC)":
            spec_info = st.text_input("Wheelchair Model Designation", "Power-Chair Alpha")
        else:
            spec_info = st.text_input("Battery Energy Specification", "24V 20Ah / Lot-B")
            
        if st.button("✨ Execute Device Serialization Run", use_container_width=True):
            prefix = "WC" if device_type == "Wheelchair (WC)" else "BAT"
            generated_list = generate_next_serials(prefix, batch_size)
            
            for sn in generated_list:
                # 1. Save to Database
                if prefix == "WC":
                    cursor.execute("INSERT INTO wheelchairs (serial_number, model_type, status) VALUES (?, ?, 'Ready for Battery')", (sn, spec_info))
                else:
                    cursor.execute("INSERT INTO batteries (serial_number, capacity_batch, status) VALUES (?, ?, 'In Stock (Available)')", (sn, spec_info))
                
                # 2. Automatically Generate QR and Save as .png file on Laptop Hard Drive
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(sn)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Construct file path: generated_qrs/WC-2026-000001.png
                file_path = os.path.join(QR_FOLDER, f"{sn}.png")
                img.save(file_path)
                
            conn.commit()
            st.success(f"🎉 Successfully serialized {batch_size} units! QR images saved locally in the '{QR_FOLDER}' folder.")
            st.rerun()
            
    with gen_col2:
        st.markdown("##### 🖨️ On-Screen Print Queue (Latest Code Generated)")
        target_table = "wheelchairs" if device_type == "Wheelchair (WC)" else "batteries"
        records = cursor.execute(f"SELECT serial_number FROM {target_table} ORDER BY serial_number DESC LIMIT 1").fetchall()
        
        if records:
            sn_str = records[0][0]
            file_path = os.path.join(QR_FOLDER, f"{sn_str}.png")
            
            if os.path.exists(file_path):
                qr_col1, qr_col2 = st.columns([1, 3])
                with qr_col1:
                    st.image(file_path)
                with qr_col2:
                    st.markdown(f"**Current Label:** `{sn_str}`")
                    st.caption("This image and all previous codes are safely archived on your computer storage.")
                    st.info(f"📂 Saved Location: `Lab-Inventory/{QR_FOLDER}/{sn_str}.png`")
        else:
            st.info("No serialized records detected in tracking ledger yet.")

# ==========================================
# TAB 3: PRODUCTION FLOOR (ASSEMBLE)
# ==========================================
with tab_assembly:
    st.subheader("🔧 Component Serialization Marriage Station")
    st.write("Scan physical barcodes or use the selector overrides to lock in the target parts.")
    
    if 'persistent_wc' not in st.session_state: st.session_state.persistent_wc = "None"
    if 'persistent_bat' not in st.session_state: st.session_state.persistent_bat = "None"
    
    available_wcs = ["None"] + [row[0] for row in cursor.execute("SELECT serial_number FROM wheelchairs WHERE status='Ready for Battery'").fetchall()]
    available_bats = ["None"] + [row[0] for row in cursor.execute("SELECT serial_number FROM batteries WHERE status='In Stock (Available)'").fetchall()]
    
    sc_col1, sc_col2 = st.columns(2)
    
    with sc_col1:
        st.markdown("### 🛒 Active Work-Order Selection")
        
        selected_wc_dropdown = st.selectbox(
            "♿ Target Wheelchair Serial:", 
            options=available_wcs,
            index=available_wcs.index(st.session_state.persistent_wc) if st.session_state.persistent_wc in available_wcs else 0
        )
        st.session_state.persistent_wc = selected_wc_dropdown
        
        selected_bat_dropdown = st.selectbox(
            "🔋 Target Battery Serial:", 
            options=available_bats,
            index=available_bats.index(st.session_state.persistent_bat) if st.session_state.persistent_bat in available_bats else 0
        )
        st.session_state.persistent_bat = selected_bat_dropdown
        
        st.markdown("---")
        
        if st.session_state.persistent_wc != "None" and st.session_state.persistent_bat != "None":
            st.info(f"Ready to assemble. Bounding Unit {st.session_state.persistent_bat} into frame {st.session_state.persistent_wc}.")
            if st.button("💾 Bind Component Assembly & Commit to Database", use_container_width=True):
                cursor.execute("UPDATE wheelchairs SET status='Assembled', installed_battery_serial=? WHERE serial_number=?", (st.session_state.persistent_bat, st.session_state.persistent_wc))
                cursor.execute("UPDATE batteries SET status='Installed', assigned_wheelchair_serial=? WHERE serial_number=?", (st.session_state.persistent_wc, st.session_state.persistent_bat))
                conn.commit()
                st.success(f"🎉 Successful Bind Entry saved to DB!")
                st.session_state.persistent_wc = "None"
                st.session_state.persistent_bat = "None"
                st.rerun()
        else:
            st.warning("⚠️ Please scan or choose both a valid Wheelchair and a Battery serial number.")

    with sc_col2:
        st.markdown("##### 📷 Live Webcam Reader Control")
        run_cam = st.checkbox("Turn On Laptop Camera Sensor Feed", key="cam_assemble_active")
        
        if run_cam:
            cap = cv2.VideoCapture(0)
            detector = cv2.QRCodeDetector()
            st_frame = st.empty()
            
            while run_cam:
                ret, frame = cap.read()
                if not ret: break
                
                data, bbox, _ = detector.detectAndDecode(frame)
                if data:
                    if data.startswith("WC-") and data in available_wcs:
                        st.session_state.persistent_wc = data
                        st.toast(f"Frame Decoded: {data}", icon="♿")
                        cap.release()
                        st.rerun()
                    elif data.startswith("BAT-") and data in available_bats:
                        st.session_state.persistent_bat = data
                        st.toast(f"Battery Decoded: {data}", icon="🔋")
                        cap.release()
                        st.rerun()
                
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                st_frame.image(img_rgb, channels="RGB", width=380)
            cap.release()

# ==========================================
# TAB 4: LOGISTICS HUB (CUSTOMER DISPATCH)
# ==========================================
with tab_dispatch:
    st.subheader("🚚 Outbound Order Fulfillment Logistics")
    
    available_assembled_wcs = ["None"] + [row[0] for row in cursor.execute("SELECT serial_number FROM wheelchairs WHERE status='Assembled'").fetchall()]
    if 'dispatch_wc' not in st.session_state: st.session_state.dispatch_wc = "None"
    
    disp_col1, disp_col2 = st.columns(2)
    with disp_col1:
        customer = st.text_input("Receiving Corporate Client / Customer Name")
        ship_date = st.date_input("Logistics Freight Dispatch Date")
        
        selected_disp_wc = st.selectbox(
            "📦 Select Target Wheelchair Serial for Dispatch:",
            options=available_assembled_wcs,
            index=available_assembled_wcs.index(st.session_state.dispatch_wc) if st.session_state.dispatch_wc in available_assembled_wcs else 0
        )
        st.session_state.dispatch_wc = selected_disp_wc
        
        if st.session_state.dispatch_wc != "None":
            record_info = cursor.execute("SELECT installed_battery_serial FROM wheelchairs WHERE serial_number=?", (st.session_state.dispatch_wc,)).fetchone()
            st.info(f"✅ Assembly Verification: Contains Linked Battery {record_info[0]}")
            
            if st.button("🚚 Commit Dispatch Record to Client Ledger", use_container_width=True):
                if customer.strip() == "":
                    st.error("Please enter a valid customer name.")
                else:
                    cursor.execute("UPDATE wheelchairs SET status='Dispatched to Customer', dispatch_date=?, customer_name=? WHERE serial_number=?", (str(ship_date), customer, st.session_state.dispatch_wc))
                    conn.commit()
                    st.success(f"Logistics registered! Shipped item to {customer}.")
                    st.session_state.dispatch_wc = "None"
                    st.rerun()
                    
    with disp_col2:
        st.markdown("##### 📷 Outbound Dock Scanner")
        run_cam_disp = st.checkbox("Turn On Shipping Camera Sensor Feed", key="cam_ship_active")
        
        if run_cam_disp:
            cap_d = cv2.VideoCapture(0)
            detector_d = cv2.QRCodeDetector()
            st_frame_d = st.empty()
            
            while run_cam_disp:
                ret, frame = cap_d.read()
                if not ret: break
                
                data, bbox, _ = detector_d.detectAndDecode(frame)
                if data and data.startswith("WC-") and data in available_assembled_wcs:
                    st.session_state.dispatch_wc = data
                    st.toast(f"Shipping scan loaded: {data}")
                    cap_d.release()
                    st.rerun()
                    
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                st_frame_d.image(img_rgb, channels="RGB", width=380)
            cap_d.release()