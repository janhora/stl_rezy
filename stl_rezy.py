import streamlit as st
import trimesh
import io
import zipfile
import numpy as np
import xml.etree.ElementTree as ET

# Nastavení vzhledu webové stránky
st.set_page_config(page_title="STL na SVG Slicer", layout="centered")
st.title("✂️ STL na SVG Slicer pro laser")
st.write("Nahrajte STL model, nastavte parametry a stáhněte si SVG vrstvy pro vyřezání z kartonu.")

# 1. Ovládací prvky v bočním panelu (Sidebar)
st.sidebar.header("Parametry řezání")
thickness = st.sidebar.slider("Tloušťka kartonu / vrstvy (mm)", min_value=0.5, max_value=20.0, value=3.0, step=0.1)
hole_dia = st.sidebar.slider("Průměr polohovacích děr (mm)", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
st.sidebar.info("Díry se automaticky vyvrtají vertikálně skrz celý model.")

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
            f"X: {extents:.1f}mm, "
            f"Y: {extents:.1f}mm, "
            f"Z: {extents:.1f}mm"
        )
        
        # Tlačítko pro spuštění zpracování
        if st.button("Spustit řezání a generování SVG"):
            with st.spinner("Zpracovávám model a generuji řezy..."):
                
                # Výpočet stabilní pozice děr (rozteč dáme jako 25% šířky modelu v ose X od středu)
                hole_distance = extents * 0.25
                hole1_x = center - hole_distance
                hole2_x = center + hole_distance
                hole_y = center
                
                # Začátek řezání od spodní hranice Z po horní hranici Z
                z_min, z_max = bounds, bounds
                z_levels = np.arange(z_min + (thickness/2), z_max, thickness)
                
                if len(z_levels) == 0:
                    st.error("Model je příliš tenký pro zvolenou tloušťku kartonu. Zmenšete tloušťku vrstvy.")
                else:
                    # Příprava ZIP archivu v paměti
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        
                        for i, z in enumerate(z_levels):
                            # Provedení 3D řezu rovinou v dané výšce Z
                            section = mesh.section(plane_origin=[0, 0, z], plane_normal=)
                            
                            if section is not None:
                                # Převod 3D řezu do 2D
                                planar, to_3d = section.to_planar()
                                
                                # Získání 2D ohraničení (bounding boxu) pro správné nastavení rozměrů SVG
                                p_bounds = planar.bounds
                                p_extents = planar.extents
                                
                                # Export základního obrysu do SVG řetězce
                                svg_string = planar.export(file_type='svg')
                                
                                # Oprava hlavičky SVG, aby Inkscape správně pochopil mm
                                # Trimesh generuje viewBox, ale my mu musíme natvrdo vnutit width a height v "mm"
                                try:
                                    # Najdeme šířku a výšku z trimesh exportu nebo použijeme rozměry polygonu
                                    width_mm = max(p_extents, 1.0)
                                    height_mm = max(p_extents, 1.0)
                                    
                                    # Vložíme explicitní jednotky mm hned na začátek <svg značky
                                    if 'width="' in svg_string:
                                        # Odstraníme staré width/height definované trimeshem, které mátly Inkscape
                                        root = ET.fromstring(svg_string)
                                        viewbox = root.get('viewBox', f"0 0 {width_mm} {height_mm}")
                                        
                                        # Sestavíme novou čistou hlavičku
                                        new_header = f'<svg xmlns="http://w3.org" width="{width_mm}mm" height="{height_mm}mm" viewBox="{viewbox}">'
                                        # Nahradíme původní otevírací tag <svg ... >
                                        header_end = svg_string.find('>')
                                        svg_string = new_header + svg_string[header_end+1:]
                                except Exception:
                                    pass # Pokud parsování selže, necháme původní string
                                
                                # Transformace 3D souřadnic děr do lokálních 2D souřadnic daného řezu
                                to_2d_matrix = trimesh.transformations.inverse_matrix(to_3d)
                                center_2d = trimesh.transformations.transform_points([
                                    [hole1_x, hole_y, z],
                                    [hole2_x, hole_y, z]
                                ], to_2d_matrix)
                                
                                # Vstřiknutí SVG elementů pro kružnice (polohovací díry)
                                r_hole = hole_dia / 2.0
                                circles_svg = ""
                                for pt in center_2d:
                                    circles_svg += f'\n<circle cx="{pt}" cy="{pt}" r="{r_hole}" stroke="black" stroke-width="0.1" fill="none" />'
                                
                                # Vložení kružnic na konec souboru před uzavírací značku </svg>
                                if "</svg>" in svg_string:
                                    svg_string = svg_string.replace("</svg>", f"{circles_svg}\n</svg>")
                                
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
