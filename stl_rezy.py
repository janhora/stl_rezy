import streamlit as st
import trimesh
import io
import zipfile
import numpy as np

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
        
        st.success(# Zobrazení základních info o modelu
            f"Model úspěšně načten! Rozměry: "
            f"X: {mesh.extents[0]:.1f}mm, "
            f"Y: {mesh.extents[1]:.1f}mm, "
            f"Z: {mesh.extents[2]:.1f}mm"
        )
        
        # Tlačítko pro spuštění zpracování
        if st.button("Spustit řezání a generování SVG"):
            with st.spinner("Zpracovávám model a vrtám díry..."):
                
                # Výpočet pozice děr (rozteč dáme jako 50% šířky modelu v ose X)
                bounds = mesh.bounds
                center = mesh.centroid
                size_x = mesh.extents[0]
                hole_distance = size_x * 0.25  # vzdálenost od středu na každou stranu
                
                hole_y = center[1]
                hole_z_min = bounds[0][2] - 5  # mírný přesah dolů pro čistý řez
                hole_z_max = bounds[1][2] + 5  # mírný přesah nahoru
                
                # Vytvoření dvou válců pro polohovací díry
                r_hole = hole_dia / 2.0
                h_hole = hole_z_max - hole_z_min
                
                cylinder_1 = trimesh.creation.cylinder(radius=r_hole, height=h_hole)
                cylinder_1.apply_translation([center[0] - hole_distance, hole_y, (hole_z_min + hole_z_max)/2])
                
                cylinder_2 = trimesh.creation.cylinder(radius=r_hole, height=h_hole)
                cylinder_2.apply_translation([center[0] + hole_distance, hole_y, (hole_z_min + hole_z_max)/2])
                
                # Booleovský rozdíl - vyvrtání děr do původního STL
                # (Pozn: Trimesh vyžaduje knihovnu blender nebo openpyscad pro složité operace, 
                # alternativně můžeme díry odečíst až ve 2D rovině řezu, což je stabilnější!)
                
                # Začátek řezání od spodní hranice Z po horní hranici Z
                z_min, z_max = bounds[0][2], bounds[1][2]
                z_levels = np.arange(z_min + (thickness/2), z_max, thickness)
                
                # Příprava ZIP archivu v paměti
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    
                    for i, z in enumerate(z_levels):
                        # Provedení 3D řezu rovinou v dané výšce Z
                        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
                        
                        if section is not None:
                            # Převod 3D řezu do 2D entit (polygony)
                            planar, to_3d = section.to_planar()
                            
                            # Vložení 2D kružnic reprezentujících otvory přímo do 2D plánu vrstvy
                            # Tím se vyhneme nespolehlivému 3D booleovskému odečítání
                            center_2d = trimesh.transformations.transform_points([
                                [center[0] - hole_distance, hole_y, z],
                                [center[0] + hole_distance, hole_y, z]
                            ], trimesh.transformations.inverse_matrix(to_3d))
                            
                            # Vytvoření kružnic ve 2D a jejich přidání jako vnitřní cesty (díry)
                            for c_point in center_2d:
                                hole_poly = trimesh.path.polygons.Creation.circle(radius=r_hole, center=c_point[:2])
                                # Odečtení kruhu od stávajícího polygonu vrstvy
                                planar.polygons = [p.difference(hole_poly) for p in planar.polygons]
                            
                            # Export vrstvy do SVG řetězce
                            svg_string = planar.export(file_type='svg')
                            
                            # Uložení do ZIPu
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
