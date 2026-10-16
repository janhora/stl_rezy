import streamlit as st
import trimesh
import io
import zipfile
import numpy as np

# Nastavení vzhledu webové stránky
st.set_page_config(page_title="STL na SVG Slicer", layout="centered")
st.title("✂️ STL na SVG Slicer pro laser (Opravená verze)")
st.write("Nahrajte STL model, nastavte parametry a stáhněte si SVG vrstvy v přesném měřítku 1:1 pro Inkscape a laser.")

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
            f"Model úspěšně načten! Skutečné rozměry: "
            f"X: {extents[0]:.1f}mm, "
            f"Y: {extents[1]:.1f}mm, "
            f"Z: {extents[2]:.1f}mm"
        )
        
        # Tlačítko pro spuštění zpracování
        if st.button("Spustit řezání a generování SVG"):
            with st.spinner("Zpracovávám model a generuji řezy..."):
                
                # Výpočet stabilní pozice děr v osách X a Y (v absolutních mm podle modelu)
                hole_distance = extents[0] * 0.25
                hole1_x = center[0] - hole_distance
                hole2_x = center[0] + hole_distance
                hole_y = center[1]
                
                # Začátek řezání od spodní hranice Z po horní hranici Z
                z_min, z_max = bounds[0][2], bounds[1][2]
                z_levels = np.arange(z_min + (thickness/2), z_max, thickness)
                
                if len(z_levels) == 0:
                    st.error("Model je příliš tenký pro zvolenou tloušťku kartonu. Zmenšete tloušťku vrstvy.")
                else:
                    # Příprava ZIP archivu v paměti
                    zip_buffer = io.BytesIO()
                    
                    # Pro bounding box celého dokumentu použijeme rozměry modelu s mírným okrajem
                    margin = 10.0
                    box_x_min, box_y_min = bounds[0][0] - margin, bounds[0][1] - margin
                    box_width = extents[0] + (2 * margin)
                    box_height = extents[1] + (2 * margin)
                    
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        
                        for i, z in enumerate(z_levels):
                            # Provedení 3D řezu rovinou v dané výšce Z
                            section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
                            
                            if section is not None:
                                # Převod 3D řezu do 2D entit (čisté polygony/křivky)
                                planar, to_3d = section.to_planar()
                                
                                # Vygenerujeme si vlastní čisté SVG s korektní jmennou hiearchií W3C
                                svg_lines = []
                                svg_lines.append(f'<svg xmlns="http://w3.org" width="{box_width}mm" height="{box_height}mm" viewBox="{box_x_min} {box_y_min} {box_width} {box_height}">')
                                
                                # Projdeme všechny křivky (polygony) v řezu a vygenerujeme pro ně <path> tagy
                                # Transformujeme 2D polygony zpět do původních souřadnic modelu X, Y, abychom neztratili měřítko 1:1
                                for path_3d in section.discrete:
                                    if len(path_3d) > 1:
                                        d_string = f"M {path_3d[0][0]},{path_3d[0][1]}"
                                        for pt in path_3d[1:]:
                                            d_string += f" L {pt[0]},{pt[1]}"
                                        d_string += " Z"
                                        svg_lines.append(f'  <path d="{d_string}" stroke="blue" stroke-width="0.2" fill="none" />')
                                
                                # Přidáme dvě polohovací díry jako perfektní kružnice s poloměrem v milimetrech
                                r_hole = hole_dia / 2.0
                                svg_lines.append(f'  <circle cx="{hole1_x}" cy="{hole_y}" r="{r_hole}" stroke="red" stroke-width="0.2" fill="none" />')
                                svg_lines.append(f'  <circle cx="{hole2_x}" cy="{hole_y}" r="{r_hole}" stroke="red" stroke-width="0.2" fill="none" />')
                                
                                # Uzavření SVG dokumentu
                                svg_lines.append('</svg>')
                                svg_string = "\n".join(svg_lines)
                                
                                # Uložení vrstvy do ZIPu
                                file_name = f"vrstva_{i+1:03d}_z_{z:.2f}mm.svg"
                                zip_file.writestr(file_name, svg_string)
                    
                    # Příprava tlačítka pro stažení ZIPu
                    zip_buffer.seek(0)
                    st.success(f"Nářezové plány úspěšně vygenerovány! Celkem {len(z_levels)} vrstev.")
                    st.download_button(
                        label="💾 Stáhnout všechny vrstvy (ZIP)",
                        data=zip_buffer,
                        file_name="svg_vrstvy_laser.zip",
                        mime="application/zip"
                    )
                
    except Exception as e:
        st.error(f"Při zpracování došlo k chybě: {str(e)}")
