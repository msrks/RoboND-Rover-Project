import numpy as np
import cv2

# Identify pixels above the threshold
# Threshold of RGB > 160 does a nice job of identifying ground pixels only
def color_thresh(img, rgb_thresh=(160, 160, 160)):
    # Create an array of zeros same xy size as img, but single channel
    color_select = np.zeros_like(img[:,:,0])
    # Require that each pixel be above all three threshold values in RGB
    # above_thresh will now contain a boolean array with "True"
    # where threshold was met
    above_thresh = (img[:,:,0] > rgb_thresh[0]) \
                & (img[:,:,1] > rgb_thresh[1]) \
                & (img[:,:,2] > rgb_thresh[2])
    # Index the array of zeros with the boolean array and set to 1
    color_select[above_thresh] = 1
    # Return the binary image
    return color_select

# Define a function to convert from image coords to rover coords
def rover_coords(binary_img):
    # Identify nonzero pixels
    ypos, xpos = binary_img.nonzero()
    # Calculate pixel positions with reference to the rover position being at the
    # center bottom of the image.
    x_pixel = -(ypos - binary_img.shape[0]).astype(np.float)
    y_pixel = -(xpos - binary_img.shape[1]/2 ).astype(np.float)
    return x_pixel, y_pixel


# Define a function to convert to radial coords in rover space
def to_polar_coords(x_pixel, y_pixel):
    # Convert (x_pixel, y_pixel) to (distance, angle)
    # in polar coordinates in rover space
    # Calculate distance to each pixel
    dist = np.sqrt(x_pixel**2 + y_pixel**2)
    # Calculate angle away from vertical for each pixel
    angles = np.arctan2(y_pixel, x_pixel)
    return dist, angles

# Define a function to map rover space pixels to world space
def rotate_pix(xpix, ypix, yaw):
    # Convert yaw to radians
    yaw_rad = yaw * np.pi / 180
    xpix_rotated = (xpix * np.cos(yaw_rad)) - (ypix * np.sin(yaw_rad))

    ypix_rotated = (xpix * np.sin(yaw_rad)) + (ypix * np.cos(yaw_rad))
    # Return the result
    return xpix_rotated, ypix_rotated

def translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale):
    # Apply a scaling and a translation
    xpix_translated = (xpix_rot / scale) + xpos
    ypix_translated = (ypix_rot / scale) + ypos
    # Return the result
    return xpix_translated, ypix_translated


# Define a function to apply rotation and translation (and clipping)
# Once you define the two functions above this function should work
def pix_to_world(xpix, ypix, xpos, ypos, yaw, world_size, scale):
    # Apply rotation
    xpix_rot, ypix_rot = rotate_pix(xpix, ypix, yaw)
    # Apply translation
    xpix_tran, ypix_tran = translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale)
    # Perform rotation, translation and clipping all at once
    x_pix_world = np.clip(np.int_(xpix_tran), 0, world_size - 1)
    y_pix_world = np.clip(np.int_(ypix_tran), 0, world_size - 1)
    # Return the result
    return x_pix_world, y_pix_world

# Define a function to perform a perspective transform
def perspect_transform(img, src, dst):

    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (img.shape[1], img.shape[0]))# keep same size as input image

    return warped

def get_rocks(img):
    color_select = np.zeros_like(img[:,:,0])
    rock_thresh = (img[:,:,0] > 100) \
                & (img[:,:,1] > 100) \
                & (img[:,:,2] < 60)
    color_select[rock_thresh] = 1
    return color_select

def get_obstacles(img):
    color_select = np.zeros_like(img[:,:,0])
    rock_thresh = (img[:,:,0] < 110) \
                & (img[:,:,1] < 110) \
                & (img[:,:,2] < 130)
    color_select[rock_thresh] = 1
    return color_select

def get_ground(img):
    color_select = np.zeros_like(img[:,:,0])
    rock_thresh = (img[:,:,0] > 160) \
                & (img[:,:,1] > 160) \
                & (img[:,:,2] > 140)
    color_select[rock_thresh] = 1
    return color_select

# Apply the above functions in succession and update the Rover state accordingly
def perception_step(Rover):
    # Perform perception steps to update Rover()
    # TODO:
    # NOTE: camera image is coming to you in Rover.img
    img = Rover.img

    # 1) Define source and destination points for perspective transform
    h = Rover.vision_image.shape[0]
    w = Rover.vision_image.shape[1]
    dst_size = 5
    bottom_offset = 6

    src = np.float32([[14, 140], [301 ,140],[200, 96], [118, 96]])
    dst = np.float32([[w/2 - dst_size, h - bottom_offset],
                      [w/2 + dst_size, h - bottom_offset],
                      [w/2 + dst_size, h - 2*dst_size - bottom_offset],
                      [w/2 - dst_size, h - 2*dst_size - bottom_offset]])

    # 2) Apply perspective transform
    warped = perspect_transform(img, src, dst)

    # 3) Apply color threshold to identify navigable terrain/obstacles/rock samples
    im_terr = get_ground(warped)
    im_rock = get_rocks(warped)
    im_obst = get_obstacles(warped)

    # 4) Update Rover.vision_image (this will be displayed on left side of screen)
    Rover.vision_image[:,:,0] = im_obst * 255
    Rover.vision_image[:,:,1] = im_rock * 255
    Rover.vision_image[:,:,2] = im_terr * 255

    # 5) Convert map image pixel values to rover-centric coords
    xpix_terr, ypix_terr = rover_coords(im_terr)
    xpix_rock, ypix_rock = rover_coords(im_rock)
    xpix_obst, ypix_obst = rover_coords(im_obst)

    # 6) Convert rover-centric pixel values to world coordinates
    xpos = Rover.pos[0]
    ypos = Rover.pos[1]
    yaw = Rover.yaw
    world_size = Rover.worldmap.shape[1]
    scale = 10

    x_world_terr, y_world_terr = pix_to_world(xpix_terr, ypix_terr, xpos, ypos,
                                              yaw, world_size, scale)
    x_world_rock, y_world_rock = pix_to_world(xpix_rock, ypix_rock, xpos, ypos,
                                              yaw, world_size, scale)
    x_world_obst, y_world_obst = pix_to_world(xpix_obst, ypix_obst, xpos, ypos,
                                              yaw, world_size, scale)

    # 7) Update Rover worldmap (to be displayed on right side of screen)
    Rover.worldmap[y_world_obst, x_world_obst, 0] += 1
    Rover.worldmap[y_world_rock, x_world_rock, 1] += 1
    Rover.worldmap[y_world_terr, x_world_terr, 2] += 1

    # 8) Convert rover-centric pixel positions to polar coordinates
    dist_terr, angles_terr = to_polar_coords(xpix_terr, ypix_terr)
    dist_rock, angles_rock = to_polar_coords(xpix_rock, ypix_rock)
    # Update Rover pixel distances and angles
    Rover.rock_dists = dist_rock
    Rover.rock_angles = angles_rock
    Rover.nav_dists = np.concatenate((dist_terr, dist_rock))
    Rover.nav_angles = np.concatenate((angles_terr, angles_rock))

    return Rover
