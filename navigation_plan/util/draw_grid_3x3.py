import cv2
import numpy as np

def draw_grid_3x3(frame, center_cell_size=(100, 100)):
    frame_height, frame_width = frame.shape[:2]
    center_w, center_h = center_cell_size
    
    side_w = (frame_width - center_w) // 2
    side_h = (frame_height - center_h) // 2

    vertical_lines = [side_w, side_w + center_w]
    horizontal_lines = [side_h, side_h + center_h]
    
    for x in vertical_lines:
        cv2.line(frame, (x, 0), (x, frame_height), (255, 255, 255), 1)
    
    for y in horizontal_lines:
        cv2.line(frame, (0, y), (frame_width, y), (255, 255, 255), 1)

    return frame


def highlight_cell(frame, cell=(1, 1), center_cell_size=(100,100), alpha=0.5):
    if not cell or not len(cell): return
    
    frame_height, frame_width = frame.shape[:2]
    center_w, center_h = center_cell_size
    
    side_w = (frame_width - center_w) // 2
    side_h = (frame_height - center_h) // 2

    cells = [
        [(0, 0), (side_w, side_h)],                                            # Top-left
        [(side_w, 0), (side_w + center_w, side_h)],                            # Top-center
        [(side_w + center_w, 0), (frame_width, side_h)],                       # Top-right
        [(0, side_h), (side_w, side_h + center_h)],                            # Middle-left
        [(side_w, side_h), (side_w + center_w, side_h + center_h)],            # Center
        [(side_w + center_w, side_h), (frame_width, side_h + center_h)],       # Middle-right
        [(0, side_h + center_h), (side_w, frame_height)],                      # Bottom-left
        [(side_w, side_h + center_h), (side_w + center_w, frame_height)],      # Bottom-center
        [(side_w + center_w, side_h + center_h), (frame_width, frame_height)]  # Bottom-right
    ]
    
    # Get the cell coordinates to highlight based on the index (row, col)
    top_left, bottom_right = cells[cell[1] + 3 * cell[0]]  # Flatten the 3x3 grid into 1D list

    # Create an overlay for semi-transparency
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, (255, 255, 255), -1)

    # Apply the overlay with alpha blending
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    return frame
