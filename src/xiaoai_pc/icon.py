"""XiaoAI artwork shared by the window, tray, and Windows packager."""
from PIL import Image, ImageDraw


def app_image(size=64):
    canvas = Image.new("RGBA", (256, 256))
    pen = ImageDraw.Draw(canvas)
    ink = "#291607"
    pen.rounded_rectangle((1, 1, 254, 254), radius=62, fill="#ff800d")
    pen.ellipse((33, 50, 222, 237), outline=ink, width=10)
    pen.arc((116, 10, 148, 80), 130, 242, fill=ink, width=10)
    leaf = [(124, 56), (132, 40), (146, 26), (163, 19), (180, 17),
            (206, 21), (198, 37), (185, 52), (169, 61), (148, 63)]
    pen.polygon(leaf, fill="#86bb43")
    pen.line(leaf + [leaf[0]], fill=ink, width=7, joint="curve")
    # Five rounded sound bars stay distinguishable at small Windows icon sizes.
    for x, height in [(75, 27), (101, 58), (127, 90), (153, 58), (179, 27)]:
        pen.rounded_rectangle((x - 7, 144 - height // 2, x + 7, 144 + height // 2),
                              radius=7, fill=ink)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)
