# Import libraries
import streamlit as st
import numpy as np
from PIL import Image
import cv2 as cv
from statistics import median
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import pdfkit

# Page configuration
ic = Image.open('figs/bar-chart-icon.png')
st.set_page_config(layout="wide", page_icon=ic,
                   page_title="Análisis de Gotas")


def process_image(input_image, input_length):
    # Manipulating input image
    input_img_np = np.array(input_image)
    height, width = input_img_np.shape[:2]
    img_gray = cv.cvtColor(input_img_np, cv.COLOR_RGB2GRAY)
    img_gray2 = cv.cvtColor(img_gray, cv.COLOR_GRAY2BGR)

    # Finding & drawing contours
    img_threshed = cv.adaptiveThreshold(img_gray, 255, cv.ADAPTIVE_THRESH_MEAN_C,
                                        cv.THRESH_BINARY_INV, 81, 3)
    contours = cv.findContours(img_threshed, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)[-2]

    contour_drawing = cv.drawContours(img_gray2, contours, -1, (0, 255, 0), 3)
    out_contours = Image.fromarray(contour_drawing)

    # Calculating summary statistics
    diameters = []
    for contour in contours:
        (x, y), r = cv.minEnclosingCircle(contour)
        # ctr = (int(x), int(y))
        d = 2 * int(r)
        diameters.append(d)

    drop_count = len(contours)

    drops_surface = 0
    for contour in contours:
        drops_surface += cv.contourArea(contour)

    drop_cover = (100 * drops_surface) / (height * width)

    if height >= width:
        px_per_mm = height / input_length
        px_per_cm = 10 * px_per_mm
    else:
        px_per_mm = width / input_length
        px_per_cm = 10 * px_per_mm

    diameters_mm = []
    for diameter in diameters:
        d_mm = diameter / px_per_mm
        diameters_mm.append(d_mm)

    median_d = median(diameters_mm)
    min_d = min(diameters_mm)
    max_d = max(diameters_mm)

    cm2 = (height / px_per_cm) * (width / px_per_cm)
    drops_per_cm2 = drop_count / cm2

    # Creating a histogram
    # First step: calculate Freedman–Diaconis number of bins
    q25, q75 = np.percentile(diameters_mm, [25, 75])
    bin_width = 2 * (q75 - q25) * len(diameters_mm) ** (-1 / 3)
    fd_bins = round((max_d - min_d) / bin_width)
    # Second step: create chart
    fig, ax = plt.subplots()
    ax.hist(diameters_mm, bins=fd_bins)
    ax.set_title('Distribución de tamaños de gota')
    ax.set_ylabel("Frecuencia (no)")
    ax.set_xlabel("Diámetro (mm)")

    return (drop_count, median_d, drops_per_cm2, drop_cover,
            out_contours, fig)


def main():
    st.header("Esta *web app* te permite analizar el papel hidrosensible "
              "utilizado en calibración de equipos pulverizadores")
    st.header("← Sube tu propia imagen para comenzar")

    # Creating input widgets
    st.sidebar.title("Análisis de Gotas")
    uploaded_img = st.sidebar.file_uploader("SUBE TU ARCHIVO", type=["jpg", "jpeg", "png"])
    mm = st.sidebar.number_input("INGRESA EL LARGO DE TU IMAGEN (mm)",
                                 min_value=1, max_value=1000, value=76)
    st.sidebar.text("")
    st.sidebar.text("")

    if uploaded_img is None:
        original_img = Image.open("muestra/papel70.png")
    else:
        original_img = Image.open(uploaded_img) # RBG

    # Image processing
    conteo, diametro, densidad, cobertura, img_procesada, grafico = process_image(original_img, mm)

    # Displaying stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.text_area(label="Gotas detectadas", value=conteo)
    with col2:
        st.text_area(label="Diámetro medio de gotas (mm)", value=round(diametro, 2))
    with col3:
        st.text_area(label="Densidad (gotas/cm\u00b2)", value=round(densidad, 1))
    with col4:
        st.text_area(label="Tasa de cobertura (% del área)", value=round(cobertura, 1))

    # Displaying images
    left, right = st.columns(2)
    with left:
        st.text("Imagen Original")
        st.image(original_img, use_column_width=True)
    with right:
        st.text("Imagen Procesada")
        st.image(img_procesada, use_column_width=True)

    # Displaying PyPlot chart
    st.pyplot(grafico)

    # Convert chart to PNG (base64 encoded)
    tmpfile = BytesIO()
    plt.savefig(tmpfile, format="PNG")
    tmpfile.seek(0)
    base64_png = base64.b64encode(tmpfile.read()).decode()

    # HTML to PDF
    formato = {'page-size': 'Letter',
               'margin-top': '1in',
               'margin-right': '0.75in',
               'margin-bottom': '0.75in',
               'margin-left': '1.5in',
               'encoding': 'UTF-8',
               'no-outline': None}

    contenido_html = f"""
    <html>
      <head><title>Resultados del an&aacute;lisis de gotas</title></head>
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
            <img src="data:image/png;base64, {base64_png}">
          </td></tr>
        </table>
      </body>
    </html>
    """

    # Set the path to wkhtmltopdf executable file
    # path_wkhtmltopdf = '/usr/local/bin/wkhtmltopdf'
    config = pdfkit.configuration()

    # if upload is not none...
    pdf_bytes = pdfkit.from_string(contenido_html, False,
                                   configuration=config, options=formato)

    st.sidebar.text("")
    st.sidebar.text("DESCARGA TUS RESULTADOS")
    st.sidebar.download_button(label='Bajar PDF', data=pdf_bytes,
                       file_name="resultados.pdf", mime='application/octet-stream')



# Run main function
if __name__ == "__main__":
    main()
