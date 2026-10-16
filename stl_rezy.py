import streamlit as st
import trimesh
import io
import zipfile
import numpy as np

# Nastavení vzhledu webové stránky
st.set_page_config(page_title="STL na SVG Slicer", layout="centered")
st.title("✂️ STL na SVG Slicer pro laser (Opravené měřítko)")
st.write("Nahrajte STL model, nastavte parametry a stáhněte si SVG vrstvy v přesném měřítku 1:1 pro Inkscape.")

# 1. Ovládací prvky v bočním panelu (Sidebar)
st.sidebar.header("Parametry řezání")
thickness = st.sidebar.slider("Tloušťka kartonu / vrstvy (mm)", min_value=0.5, max_value=20.0, value=3.0, step=0.1)
hole_dia = st.sidebar.slider("Průměr polohovacích děr (mm)", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
st.sidebar.info("Měřítko je pevně uzamčeno na 1 jednotka STL = 1 mm.")

# 2. Nahrání souboru
uploaded_file = st.file_uploader("Vyberte 3D model ve formátu .stl", type=["stl"])

if uploaded_file is not None:
    try:
        # Načtení STL z paměti
        file_bytes = uploaded_file.read()
        mesh = trimesh.load(io.BytesIO(file_bytes), file_type='stl')
        
        # Získání rozměrů modelu
        extents = mesh.extents
        bounds = mesh.bounds
        center = mesh.centroid
        
        st.success(
            f"Model úspěšně načten! Rozměry: "
            f"X: {extents[0]:.1f}mm, "
            f"Y: {extents[1]:.1f}mm, "
            f"Z: {extents[2]:.1f}mm"
        )
        
        # Tlačítko pro spuštění zpracování
        if st.button("Spustit řezání a generování SVG"):
            with st.spinner("Zpracovávám model..."):
                
                # Výpočet pozice děr v osách X a Y (v absolutních mm, symetricky kolem středu)
                hole_distance = extents[0] * 0.25
                hole1_x = center[0] - hole_distance
                hole2_x = center[0] + hole_distance
                hole_y = center[1]
                
                # Začátek řezání od spodní hranice Z po horní hranici Z
                z_min, z_max = bounds[0][2], bounds[1][2]
                z_levels = np.arange(z_min + (thickness/2), z_max, thickness)
                
                if len(z_levels) == 0:
                    st.error("Model je příliš tenký pro zvolenou tloušťku kartonu.")
                else:
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        
                        for i, z in enumerate(z_levels):
                            section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
                            
                            if section is not None:
                                # Získání 3D křivek řezu
                                paths = section.discrete
                                
                                if len(paths) > 0:
                                    # Spočítáme dynamický bounding box pro tuto vrstvu včetně děr
                                    all_points = np.vstack(paths)[:, :2]
                                    all_points = np.vstack([all_points, [hole1_x, hole_y], [hole2_x, hole_y]])
                                    
                                    min_x, min_y = np.min(all_points, axis=0) - 5.0
                                    max_x, max_y = np.max(all_points, axis=0) + 5.0
                                    width_mm = max_x - min_x
                                    height_mm = max_y - min_y
                                    
                                    # Generování čistého, validního SVG kódu pro Inkscape
                                    svg_lines = []
                                    svg_lines.append(f'<svg xmlns="http://w3.org" width="{width_mm}mm" height="{height_mm}mm" viewBox="{min_x} {min_y} {width_mm} {height_mm}">')
                                    
                                    # Vykreslení obrysových křivek z STL
                                    for path_3d in paths:
                                        if len(path_3d) > 1:
                                            d_string = f"M {path_3d[0][0]},{path_3d[0][1]}"
                                            for pt in path_3d[1:]:
                                                d_string += f" L {pt[0]},{pt[1]}"
                                            d_string += " Z"
                                            svg_lines.append(f'  <path d="{d_string}" stroke="blue" stroke-width="0.2" fill="none" />')
                                    
                                    # Vykreslení středových děr pro špejle
                                    r_hole = hole_dia / 2.0
                                    svg_lines.append(f'  <circle cx="{hole1_x}" cy="{hole_y}" r="{r_hole}" stroke="red" stroke-width="0.2" fill="none" />')
                                    svg_lines.append(f'  <circle cx="{hole2_x}" cy="{hole_y}" r="{r_hole}" stroke="red" stroke-width="0.2" fill="none" />')
                                    
                                    svg_lines.append('</svg>')
                                    svg_string = "\n".join(svg_lines)
                                    
                                    file_name = f"vrstva_{i+1:03d}_z_{z:.2f}mm.svg"
                                    zip_file.writestr(file_name, svg_string)
                    
                    zip_buffer.seek(0)
                    st.success(f"Nářezové plány vygenerovány! Celkem {len(z_levels)} vrstev.")
                    st.download_button(
                        label="💾 Stáhnout všechny vrstvy (ZIP)",
                        data=zip_buffer,
                        file_name="svg_vrstvy_laser.zip",
                        mime="application/zip"
                    )
                
    except Exception as e:
        st.error(f"Při zpracování došlo k chybě: {str(e)}")
