# Import libraries
import os
import streamlit as st
import numpy as np
from PIL import Image
import cv2 as cv
from statistics import median
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from weasyprint import HTML

# Page configuration
if os.path.exists('figs/bar-chart-icon.png'):
    ic = Image.open('figs/bar-chart-icon.png')
    st.set_page_config(layout="wide", page_icon=ic, page_title="Análisis de Gotas")
else:
    st.set_page_config(layout="wide", page_title="Análisis de Gotas")


@st.cache_data
def compute_droplet_metrics(input_img_np, input_length):
    """Cached function to perform heavy image processing and statistical calculations."""
    height, width = input_img_np.shape[:2]
    img_gray = cv.cvtColor(input_img_np, cv.COLOR_RGB2GRAY)

    # Finding contours
    img_threshed_inv = cv.adaptiveThreshold(
        img_gray, 255, cv.ADAPTIVE_THRESH_MEAN_C,
        cv.THRESH_BINARY_INV, 81, 3
    )
    contours = cv.findContours(img_threshed_inv, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[-2]

    # Drawing contours
    img_threshed = cv.adaptiveThreshold(
        img_gray, 255, cv.ADAPTIVE_THRESH_MEAN_C,
        cv.THRESH_BINARY, 81, 3
    )
    img_thresh2bgr = cv.cvtColor(img_threshed, cv.COLOR_GRAY2BGR)
    img_contours = cv.drawContours(img_thresh2bgr, contours, -1, (0, 0, 255), 3)
    img_contours_rgb = cv.cvtColor(img_contours, cv.COLOR_BGR2RGB)

    # Calculating scale
    if height >= width:
        px_per_mm = height / input_length
    else:
        px_per_mm = width / input_length
    px_per_cm = 10 * px_per_mm

    diameters_mm = []
    for contour in contours:
        (_, _), r = cv.minEnclosingCircle(contour)
        d_px = 2 * int(r)
        d_mm = d_px / px_per_mm
        diameters_mm.append(d_mm)

    drop_count = len(contours)
    drops_surface = sum(cv.contourArea(contour) for contour in contours)
    drop_cover = (100 * drops_surface) / (height * width) if (height * width) > 0 else 0.0

    median_d = float(median(diameters_mm)) if diameters_mm else 0.0
    min_d = float(min(diameters_mm)) if diameters_mm else 0.0
    max_d = float(max(diameters_mm)) if diameters_mm else 0.0

    cm2 = (height / px_per_cm) * (width / px_per_cm) if px_per_cm > 0 else 1.0
    drops_per_cm2 = drop_count / cm2

    return drop_count, median_d, drops_per_cm2, drop_cover, diameters_mm, img_contours_rgb, min_d, max_d


def main():
    st.header("Esta *web app* te permite analizar los patrones de aspersión registrados en papel hidrosensible")
    st.header("← Sube tu propia imagen en el panel izquierdo")

    # Creating input widgets
    st.sidebar.title("Análisis de Gotas")
    uploaded_img = st.sidebar.file_uploader("SUBE TU ARCHIVO", type=["jpg", "jpeg", "png"])
    mm = st.sidebar.number_input(
        "INGRESA EL LARGO DE TU IMAGEN (mm)",
        min_value=1, max_value=1000, value=76
    )

    if uploaded_img is None:
        sample_path = "muestra/papel250.png"
        if os.path.exists(sample_path):
            original_img = Image.open(sample_path)
        else:
            st.error(f"No se encontró la imagen de muestra en '{sample_path}'. Sube una imagen para comenzar.")
            return
    else:
        original_img = Image.open(uploaded_img)

    # Convert original image to NumPy array for processing
    original_img_np = np.array(original_img)

    # Image processing and metrics computation
    conteo, diametro, densidad, cobertura, diameters_mm, img_contours_rgb, min_d, max_d = compute_droplet_metrics(
        original_img_np, mm
    )

    # Displaying stats using st.metric
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Gotas detectadas", value=conteo)
    with col2:
        st.metric(label="Diámetro medio de gotas (mm)", value=round(diametro, 2))
    with col3:
        st.metric(label="Densidad (gotas/cm²)", value=round(densidad, 1))
    with col4:
        st.metric(label="Tasa de cobertura (% del área)", value=round(cobertura, 1))

    # Fig 0: Processed image plot
    fig0 = plt.figure()
    plt.tick_params(bottom=False, left=False, labelbottom=False, labelleft=False)
    plt.imshow(img_contours_rgb)

    # Fig 1: Histogram plot
    if diameters_mm and max_d > min_d:
        q25, q75 = np.percentile(diameters_mm, [25, 75])
        bin_width = 2 * (q75 - q25) * len(diameters_mm) ** (-1 / 3) if (q75 - q25) > 0 else 1
        fd_bins = max(1, round((max_d - min_d) / bin_width)) if bin_width > 0 else 1
    else:
        fd_bins = 1

    fig1, ax = plt.subplots()
    ax.hist(diameters_mm, bins=fd_bins)
    ax.set_title('Distribución de tamaños de gota')
    ax.set_ylabel("Frecuencia (no)")
    ax.set_xlabel("Diámetro (mm)")

    # Displaying images
    left, right = st.columns(2)
    with left:
        st.text("Imagen Original")
        st.image(original_img, use_container_width=True)
    with right:
        st.text("Imagen Procesada")
        st.pyplot(fig0)

    # Displaying PyPlot chart
    st.pyplot(fig1)

    # Convert fig0 to PNG (base64 encoded)
    tmpfile0 = BytesIO()
    fig0.savefig(tmpfile0, format="PNG")
    tmpfile0.seek(0)
    base64_fig0 = base64.b64encode(tmpfile0.read()).decode()

    # Convert fig1 to PNG (base64 encoded)
    tmpfile1 = BytesIO()
    fig1.savefig(tmpfile1, format="PNG")
    tmpfile1.seek(0)
    base64_fig1 = base64.b64encode(tmpfile1.read()).decode()

    # Close Matplotlib figures to prevent memory leaks
    plt.close(fig0)
    plt.close(fig1)

    # HTML to PDF Content
    contenido_html = f"""
    <html>
      <head>
      <title>Resultados del an&aacute;lisis de gotas</title>
      </head>
      <body>
        <table style="width:100%" border="0">
          <tr><td colspan="2"><h2>Resultados del an&aacute;lisis de gotas</h2></td></tr>
          <tr><td style="width:50%">
            <p>Gotas detectadas: {conteo}</p>
            <p>Di&aacute;metro medio de gotas (mm): {diametro:.2f}</p>
          </td><td style="width:50%">
            <p>Densidad (gotas/cm&sup2;): {densidad:.2f}</p>
            <p>Tasa de cobertura (% del &aacute;rea): {cobertura:.2f}</p>
          </td></tr>
          <tr><td colspan="2">
            <img src="data:image/png;base64, {base64_fig1}">
          </td></tr>
          <tr><td colspan="2">
            <img src="data:image/png;base64, {base64_fig0}">
          </td></tr>
          <tr><td style="width:50%">
            <p>Reporte generado con la web app https://droplets.streamlit.app</p>
          </td><td style="width:50%">
          </td></tr>
        </table>
      </body>
    </html>
    """

    pdf_file = HTML(string=contenido_html).write_pdf()

    st.sidebar.text("")
    st.sidebar.text("DESCARGA TUS RESULTADOS")
    st.sidebar.download_button(
        label='Bajar PDF', data=pdf_file,
        file_name="resultados.pdf", mime='application/pdf'
    )

    st.sidebar.text("")
    st.sidebar.text("")
    st.sidebar.text("Desarrollado por  \nPatricio Brevis (2024)")


# Run main function
if __name__ == "__main__":
    main()
