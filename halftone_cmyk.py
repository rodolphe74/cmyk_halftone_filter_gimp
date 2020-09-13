#!/usr/bin/env python
from timeit import default_timer as timer
from array import array
from gimpfu import pdb
from gimpfu import gimp
from gimpfu import RGBA_IMAGE
from gimpfu import LAYER_MODE_NORMAL
from gimpfu import MULTIPLY_MODE
from gimpfu import FILL_WHITE
from gimpfu import INTERPOLATION_CUBIC
from gimpfu import register
from gimpfu import main
from gimpfu import PF_SPINNER
from gimpfu import PF_INT
from gimpfu import PF_TOGGLE
import math


# globals
COLORS = [(0, 255, 255, 255), (255, 0, 255, 255),
          (255, 255, 0, 255), (0, 0, 0, 255)]
COMPONENT_STRING = ["cyan", "magenta", "yellow", "black"]
POSSIBLE_ANGLES = [[-0.262, -1.309, 0, -0.785],
                   [-1.832, -1.309, -1.570, -0.262],
                   [-0.262, -0.785, 0, -1.309],
                   [-2.878, -0.785, -1.570, -1.832]]
ANGLES = [-0.262, -1.309, 0, -0.785]
# D = 7  # spacing between circles
# C = 8  # circle max size

PRE_ENLARGE = 800
POST_SHRINK_FLAG = False

# B = 200


def find_layer(img, layer_name):
    """ find a image layer by name """
    for layer in img.layers:
        if layer.name == layer_name:
            return layer
    return None


def draw_circle(layer, c_x, c_y, rayon, color):
    """ draw a circle on layer """
    # pdb.gimp_drawable_set_pixel(drawable, i, j, 4, pixel)
    pixel = [color[0], color[1], color[2], 255]
    for y in range(-rayon, rayon + 1):
        for x in range(-rayon, rayon + 1):
            a = x*x+y*y
            b = rayon*rayon
            if a <= b:
                pdb.gimp_drawable_set_pixel(layer, c_x + x, c_y + y, 4, pixel)
                layer.flush()


def merge_layer(img, layer_1, layer_2):
    """ merge layers """
    # keep current state
    layer_state = []
    for layer in img.layers:
        if layer != layer_1 and layer != layer_2:
            layer_state.append((layer, layer.visible))

    # set layer_1 and layer_2 visible
    for layer in img.layers:
        layer.visible = False
    layer_1.visible = True
    layer_2.visible = True

    # merge
    new_layer = pdb.gimp_image_merge_visible_layers(img, 0)

    # set old state
    for layer in layer_state:
        layer[0].visible = layer[1]

    return new_layer


def shift_left(ar, w, shift):
    """ shift screen left """
    a = array('B')
    for i in range(0, len(ar), w):
        e = ar[i:i+shift]
        d = ar[i+shift:i+w]
        a = a + d
        c = array('B', [0] * len(e))
        a = a + c
    return a


def shift_right(ar, w, shift):
    """ shift right screen """
    f = array('B')
    for i in range(0, len(ar), w):
        e = ar[i:i+shift]
        d = ar[i:i+(w-shift)]
        c = array('B', [0] * len(e))
        f = f + c + d
    return f[0:len(ar)]


def shift_up(ar, w, shift):
    """ shift region up """
    m = len(ar)/w
    shift = min(m, shift)

    i = w * shift
    e = ar[i:]

    for i in range(0, shift):
        c = array('B', [0] * w)
        e = e + c
    return e


def shift_down(ar, w, shift):
    c = array('B', [0] * w * shift)
    e = c + ar
    return e[0:len(ar)]


def draw_circle_2(img, layer, c_x, c_y, rayon, color):
    """ draw a plain circle on layer """
    start_x = c_x - rayon if c_x - rayon > 0 else 0
    start_y = c_y - rayon if c_y - rayon > 0 else 0
    width = rayon * 2
    height = rayon * 2
    print (start_x, start_y, c_x, c_y, width, height)

    # Make sure this layer supports alpha so we can write to each pixel's
    # alpha component
    layer.add_alpha()

    circle_layer = pdb.gimp_layer_new(img, layer.width, layer.height, RGBA_IMAGE, "circle",
                                      100, LAYER_MODE_NORMAL)
    pdb.gimp_image_insert_layer(img, circle_layer, None, 0)

    source_region = layer.get_pixel_rgn(
        start_x, start_y, width+1, height+1, False, False)
    pixel_size = len(source_region[start_x, start_y])
    print ("pixel_size:", pixel_size)

    region = circle_layer.get_pixel_rgn(start_x, start_y, start_x+width+1,
                                        start_y+height+1, True, True)

    pixels = array("B", "\x00" * (width * height * pixel_size))
    for y in xrange(0, height):
        for x in xrange(0, width):
            index = (x + width * y) * pixel_size
            # pixel = source_pixels[index: index + pixel_size]
            new_pixel = array('B', [color[0], color[1], color[2], 255])
            # Write the modified pixel out to our destination array
            xx = x - rayon
            yy = y - rayon
            a = xx*xx + yy*yy
            b = rayon * rayon
            if a <= b:
                pixels[index: index + pixel_size] = new_pixel

    # Copy the whole array into the writeable pixel region
    region[start_x:start_x+width, start_y:start_y+height] = pixels.tostring()

    # Write our changes back over the original layer
    circle_layer.flush()
    circle_layer.merge_shadow(True)
    circle_layer.update(start_x, start_y, width, height)

    # merge the circle layer and the background layer
    new_layer = merge_layer(img, layer, circle_layer)
    return new_layer


def get_intensity(x, y, radius):
    """ use for anti-aliasing """
    return abs((math.sqrt((x * x) + (y * y)) - float(radius)) / 1.5)


def draw_circle_on_layer(layer_dest, c_x, c_y, rayon, color):
    """ draw a circle on the layer """
    # y_1 = c_y - rayon if c_y - rayon > 0 else 0

    y_1 = c_y - rayon
    if c_y - rayon < 0:
        y_1 = 0
    elif c_y + rayon > layer_dest.height:
        y_1 = layer_dest.height - 2 * rayon

    x_1 = c_x - rayon
    if c_x - rayon < 0:
        x_1 = 0
    elif c_x + rayon > layer_dest.width:
        x_1 = layer_dest.width - 2 * rayon

    w = rayon * 2 if c_x - rayon > 0 else rayon + c_x
    h = rayon * 2 if c_y - rayon > 0 else rayon + c_y

    # layer_dest.add_alpha()

    n = 2 * rayon + 1
    region = layer_dest.get_pixel_rgn(x_1, y_1, n, n,
                                      True, True)
    pixel_size = 4
    pixels = array("B", "\x00" * (n * n * pixel_size))
    b = rayon * rayon
    new_pixel = array('B', [color[0], color[1], color[2], 255])
    for y in xrange(-rayon, rayon+1):
        for x in xrange(-rayon, rayon+1):
            a = x*x+y*y
            if a <= b:
                # draw the circle inside the delimited region
                new_x = x + rayon
                new_y = y + rayon
                index = (new_x + n * new_y) * pixel_size
                pixels[index: index + pixel_size] = new_pixel

    # shift ? (when region was set at 0,0 and the circle is not fully on the
    # screen)
    if c_x - rayon < 0:
        pixels = shift_left(pixels, 2*rayon * pixel_size, 4*abs(c_x-rayon))

    if c_y - rayon < 0:
        pixels = shift_up(pixels, 2*rayon * pixel_size, abs(c_y-rayon))

    if c_x + rayon > layer_dest.width:
        pixels = shift_right(pixels, 2*rayon * pixel_size,
                             4*abs((c_x - layer_dest.width)+rayon))

    if c_y + rayon > layer_dest.height:
        pixels = shift_down(pixels, 2*rayon * pixel_size,
                            abs((c_y - layer_dest.height)+rayon))

    region[x_1:x_1 + n, y_1:y_1 + n] = pixels.tostring()

    # Write our changes back over the original layer
    layer_dest.flush()
    layer_dest.merge_shadow(True)
    layer_dest.update(x_1, y_1, w, h)


def lighten(color, amount):
    r = int(round(min(255, color[0] + 255 * amount)))
    g = int(round(min(255, color[1] + 255 * amount)))
    b = int(round(min(255, color[2] + 255 * amount)))
    return (r, g, b)


def draw_circle_on_pixels_region(pixels, width, height, c_x, c_y, rayon, color):
    """ draw a circle on the pixels region array """
    pixel_size = 4
    b = rayon * rayon
    new_pixel = array('B', [color[0], color[1], color[2], 255])
    for y in xrange(-rayon, rayon+1):
        for x in xrange(-rayon, rayon+1):
            a = x*x+y*y
            if a <= b:
                new_x = x + c_x
                new_y = y + c_y
                if new_x >= width-1:
                    new_x = width-1
                if new_y >= height-1:
                    new_y = height-1
                if new_x <= 0:
                    new_x = 0
                if new_y <= 0:
                    new_y = 0
                index = (new_x + width * new_y) * pixel_size
                pixels[index: index + pixel_size] = new_pixel


def rotate(layer, angle):
    """ rotate a layer """
    pdb.gimp_edit_copy(layer)
    tmp_image = pdb.gimp_edit_paste_as_new()

    tmp_layer = pdb.gimp_image_get_active_layer(tmp_image)
    pdb.gimp_item_transform_rotate(
        tmp_layer, angle, False, tmp_layer.width/2, tmp_layer.height/2)
    print(tmp_layer.width, tmp_layer.height)
    pdb.gimp_image_resize(tmp_image, tmp_layer.width, tmp_layer.height, 0, 0)
    pdb.gimp_layer_set_offsets(tmp_layer, 0, 0)

    pdb.gimp_display_new(tmp_image)
    pdb.gimp_displays_flush()


def get_value_in_range(old_value, old_min, old_max, new_min, new_max):
    new_value = 0
    old_range = (old_max - old_min)
    if old_range == 0:
        new_value = new_min
    else:
        new_range = (new_max - new_min)
        new_value = (((old_value - old_min) * new_range) /
                     float(old_range)) + new_min
    return int(round(new_value))


def get_mean_brightness(pixels, box, width, height, pixel_size):
    count = 0
    sum = 0
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            index = (x + width * y) * pixel_size
            pix = pixels[index: index + pixel_size]
            if len(pix) == pixel_size:
                sum += pix[3]  # brightness
                count += 1
    return sum/count


def halftone_layer(img, layer, layer_dest, density, color, circle_size, black_strength):
    """ halftone the layer """
    gimp.progress_init("Generating " + layer_dest.name)
    circles_count = 0
    start = timer()

    source_region = layer.get_pixel_rgn(
        0, 0, layer.width, layer.height, False, False)
    pixel_size = len(source_region[0, 0])
    source_pixels = array("B", source_region[0:layer.width, 0:layer.height])
    print (pixel_size, len(source_pixels))

    region = layer_dest.get_pixel_rgn(
        0, 0, layer_dest.width, layer_dest.height, True, True)
    # pixel_size = 4
    n = layer_dest.width*layer_dest.height
    pixels = array("B", "\xFF" * (n * pixel_size))

    for i in range(0, (layer.height / density) + 1):
        for j in range(0, (layer.width / density) + 1):
            percent = ((i*layer.width + j) /
                       float((layer.height*layer.width))) * density
            gimp.progress_update(percent)
            x = j * density
            y = i * density
            x_2 = x + density if x + density < layer.width else layer.width
            y_2 = y + density if y + density < layer.height else layer.height
            if x_2 == x or y_2 == y:
                continue
            box = (x, y, x_2, y_2)
            mean_bright = get_mean_brightness(
                source_pixels, box, layer.width, layer.height, pixel_size)
            max_strength = 255
            if color == (0, 0, 0, 255):
                # manage black strength
                max_strength = 510 - black_strength

            isz = get_value_in_range(mean_bright, 0, max_strength, 0, circle_size)

            if isz > 0:
                circles_count += 1
                draw_circle_on_pixels_region(
                    pixels, layer_dest.width, layer_dest.height, x+density/2,
                    y+density/2, isz, color)

    # Write our changes back over the original layer
    region[0:layer_dest.width, 0:layer_dest.height] = pixels.tostring()
    layer_dest.flush()
    layer_dest.merge_shadow(True)
    layer_dest.update(0, 0, layer_dest.width, layer_dest.height)

    pdb.gimp_progress_end()
    end = timer()
    print (circles_count, 'in', end - start,
           float(end - start) / circles_count)


def rotate_layer(layer, angle):
    """ center rotation of the layer """
    print ("rotate " + layer.name + " of " + str(angle) + " rad")
    pdb.gimp_item_transform_rotate(
        layer, angle, False, layer.width/2, layer.height/2)


def add_cmyk_layers(img, layer):
    """ decompose layer in cmyk components """
    # Obtain layer dimensions.
    width = layer.width
    height = layer.height

    # Make sure this layer supports alpha so we can write to each pixel's alpha
    # component
    layer.add_alpha()

    for k in range(0, 4):
        # Grab a pixel region (readonly)  covering the entire image and copy
        # pixel data into an array
        source_region = layer.get_pixel_rgn(0, 0, width, height, False, False)
        source_pixels = array("B", source_region[0:width, 0:height])
        pixel_size = len(source_region[0, 0])
        print("pixel_size", pixel_size)

        # Create component layer in the Image
        component_layer = pdb.gimp_layer_new(img, width, height, RGBA_IMAGE,
                                             COMPONENT_STRING[k], 100,
                                             LAYER_MODE_NORMAL)
        pdb.gimp_image_insert_layer(img, component_layer, None, 0)
        pdb.gimp_drawable_fill(component_layer, FILL_WHITE)

        # Create another region (writeable) and an array that can store all
        # our modified pixels
        component_region = component_layer.get_pixel_rgn(
            0, 0, width, height, True, True)
        component_pixels = array("B", "\x00" * (width * height * pixel_size))

        gimp.progress_init(
            "getting " + COMPONENT_STRING[k] + " component layer...")

        x = 0
        y = 0

        # Loop through every pixel in the image/layer
        for y in xrange(0, (height-1)):
            for x in xrange(0, (width-1)):
                gimp.progress_update(1.0 * y/height)
                source_index = (x + width * y) * pixel_size
                pixel = source_pixels[source_index: source_index + pixel_size]
                # Write the modified pixel out to our destination array
                component_pixel = pixel
                # intensity = 0
                if k == 3:
                    # black specific
                    intensity = pixel[k]
                    # intensity = int(round(pixel[0] * 0.2126 +
                    # pixel[1] * 0.7152 +
                    # pixel[2] * 0.0722))

                    # c_linear = (pixel[0] / 255.0) * 0.2126
                    # + (pixel[1] / 255.0) * 0.7152
                    # + (pixel[2] / 255.0) * 0.0722
                    # intensity = 12.92 * c_linear if c_linear <= 0.0031308 else 1.055 * \
                    # pow(c_linear, 1/2.4) - 0.055
                    # intensity = int(round(intensity*255.0))

                    intensity = int(
                        round(pixel[0] * 0.299 + pixel[1] * 0.587
                              + pixel[2] * 0.114))
                else:
                    intensity = pixel[k]
                component_pixel[3] = (255 - intensity)
                component_pixel[0] = COLORS[k][0]
                component_pixel[1] = COLORS[k][1]
                component_pixel[2] = COLORS[k][2]
                component_pixels[source_index: source_index +
                                 pixel_size] = component_pixel

        # Copy the whole array into the writeable pixel region
        component_region[0:width, 0:height] = component_pixels.tostring()

        # Write our changes back over the original layer
        component_layer.flush()
        component_layer.merge_shadow(True)
        component_layer.update(0, 0, width, height)

    pdb.gimp_progress_end()
    pdb.gimp_displays_flush()


def scale_image(image, width, height):
    pdb.gimp_progress_init("Scaling Image...", None)
    pdb.gimp_context_set_interpolation(INTERPOLATION_CUBIC)
    pdb.gimp_image_scale(image, width, height)


def halftone_gimp(img, layer, slide_density, slide_circle_size, work_size_flag,
                  work_size_width, revert_size_flag, black_strength, slide_angle):
    # Obtain layer dimensions.
    width = layer.width
    height = layer.height
    print("original size:", width, height)

    print("density", slide_density)
    D = int(slide_density)

    print ("circle size", "slide_circle_size")
    C = int(slide_circle_size)

    print("black strength", black_strength)
    B = int(black_strength)

    ANGLES = POSSIBLE_ANGLES[int(slide_angle)-1]
    print("angles", ANGLES)

    # New image dimensions
    if work_size_flag is True:
        new_width = int(work_size_width)
        new_height = int(height * (new_width / float(width)))
        print("new_size:", new_width, new_height)
        scale_image(img, new_width, new_height)
    else:
        new_width = width
        new_height = height

    add_cmyk_layers(img, layer)

    halftone_layers = [None] * 4
    for k in range(0, 4):
        current_layer = find_layer(img, COMPONENT_STRING[k])
        rotate_layer(current_layer, ANGLES[k])
        halftone_layers[k] = pdb.gimp_layer_new(img, current_layer.width,
                                                current_layer.height,
                                                RGBA_IMAGE,
                                                COMPONENT_STRING[k] +
                                                " halftone",
                                                100, MULTIPLY_MODE)

        pdb.gimp_image_insert_layer(img, halftone_layers[k], None, 0)
        pdb.gimp_drawable_fill(halftone_layers[k], FILL_WHITE)

        start = timer()
        halftone_layer(img, current_layer, halftone_layers[k], D, COLORS[k], C, B)
        end = timer()
        print ("halftone in ", end-start)
        rotate_layer(halftone_layers[k], -ANGLES[k])
        x0, y0 = pdb.gimp_drawable_offsets(halftone_layers[k])
        non_empty, x1, y1, x2, y2 = pdb.gimp_selection_bounds(img)
        print (x0, y0)
        print (x1, y1, x2, y2)
        xx = new_width/2 - current_layer.width/2
        yy = new_height/2 - current_layer.height/2

        # print xx, yy
        pdb.gimp_layer_set_offsets(halftone_layers[k], x0+xx, y0+yy)

    for i_layer in COMPONENT_STRING:
        del_layer = find_layer(img, i_layer)
        img.remove_layer(del_layer)

    for i_layer in img.layers:
        if i_layer.name.endswith("halftone"):
            i_layer.visible = False
            # if revert_size_flag is True:
            #    scale_image(img, width, height)
        else:
            i_layer.visible = False

    for i_layer in img.layers:
        if i_layer.name.endswith("halftone"):
            current_layer = pdb.gimp_layer_new(img, new_width,
                                               new_height,
                                               RGBA_IMAGE,
                                               "_" + i_layer.name + "_",
                                               100, MULTIPLY_MODE)
            pdb.gimp_image_insert_layer(img, current_layer, None, 0)
            pdb.gimp_rect_select(img, 0, 0, new_width, new_height, 2, 0, 0)
            pdb.gimp_edit_copy(i_layer)
            new_layer = pdb.gimp_edit_paste(current_layer, True)
            pdb.gimp_floating_sel_anchor(new_layer)

    for i_layer in img.layers:
        if i_layer.name.endswith("halftone"):
            print (i_layer.name)
            img.remove_layer(i_layer)

    if revert_size_flag is True:
        scale_image(img, width, height)


register(
    "python_fu_halftone_cmyk",
    "Printer effect",
    "Printer effect on the current layer",
    "Rodolphe",
    "Open source (BSD 3-clause license)",
    "2020",
    "<Image>/Python-Fu/rodoc/Halftone CMYK",
    "*",
    [
        (PF_SPINNER, "slide_density", "Spacing between circles:", 14, (3, 20, 1)),
        (PF_SPINNER, "slide_circle_size", "Circles max size:", 12, (3, 20, 1)),
        (PF_TOGGLE, "work_size_flag",   "Work on specific size:", 1),
        (PF_INT, "work_size_width", "Specific width:", 2400),
        (PF_TOGGLE, "revert_size_flag",   "Revert original size:", 0),
        (PF_SPINNER, "black_strength", "Black strength [0,255]:", 150, (0, 255, 1)),
        (PF_SPINNER, "slide_angle",
         "Angles method [15,75,0,45], [105,75,90,15], [15,45,0,75], [165,45,90,105] :", 1, (1, 4, 1)),
    ],
    [],
    halftone_gimp)

main()
