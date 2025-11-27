import io

from PIL import Image
import pytesseract
import fitz

pdf_path = "../pdfdocument_extraction/Statement8312025.pdf"
pages = fitz.open(pdf_path)
text = ""
for page in pages:
    # Extract text from the page
    text = page.get_images
    all_images_bytes = []
    images = page.get_images(full=True)
    for image in images:
        try:
            xref = image[0]
            base_image = pages.extract_image(xref)
            image_bytes = base_image["image"]
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img, lang="eng")
            print(text)
            # all_images_bytes.append(image_bytes)
        except Exception as err:
            print(f"Error while processing image: ", {err})
    # text = pytesseract.image_to_string(page)
    # print(text)
# Extract images from the page
# for img_index, img in enumerate(page.get_images(full=True)):
#     xref = img[0]
#     base_image = doc.extract_image(xref)
#     image_bytes = base_image["image"]
#     images.append(image_bytes)

# text = pytesseract.image_to_string(pages[0])
