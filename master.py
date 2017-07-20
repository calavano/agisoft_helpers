import os
import glob
import re
import math
import PhotoScan

# Specify folder of unique identifier.
# Files must be in the following locations:
# [identifier]
#   \JPG\
#       \SIDEA\ -- location of jpegs for top view
#       \SIDEB\ -- location of jpegs for bottom view
#   \PROCESSING\ -- location to be used for psx file
#   \EXPORT\
#       \OBJ\
#       \PLY\

# Note that a lot of these tasks only work when chunks have specific
# labels. Many of the tasks will only work when performed at the
# appropriate times.

DOC = PhotoScan.app.document
SERVER_IP = ''
SHARED_ROOT = ''
IMAGES_FOLDER = 'JPG'
PROCESS_FOLDER = 'PROCESSING'
EXPORT_FOLDER = 'EXPORT'
MODE = 'network'
TURNTABLE = False
VALID_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'tif', 'tiff', 'png', 'bmp', 'exr',
                          'tga', 'pgm', 'ppm', 'dng', 'mpo', 'seq', 'ara']

# Handles starting a network batch jobs.
# Accepts an array of hashes of tasks/parameters.
def start_network_batch_process(chunks, tasks):
    network_tasks = []
    client = PhotoScan.NetworkClient()
    client.connect(SERVER_IP)
    for task_params in tasks:
        new_task = PhotoScan.NetworkTask()
        for chunk in chunks:
            new_task.frames.append((chunk.key, 0))
            new_task.name = task_params['name']
            for key in task_params:
                if key != 'name':
                    new_task.params[key] = task_params[key]
        network_tasks.append(new_task)
    network_save = PhotoScan.app.document.path.replace(SHARED_ROOT, '')
    batch_id = client.createBatch(network_save, network_tasks)
    client.resumeBatch(batch_id)

#
# Loads images from two 'sides', aligns cameras, and detects markers.
# This will create N chunks and load the images from SIDEA/SIDEB/SIDEN into each.
def load_images():
    path_druid = PhotoScan.app.getExistingDirectory("Specify DRUID path:")
    path_druid = path_druid.replace('\\', '/')
    druid = path_druid.split('/')[-1]
    path_photos = path_druid + '/' + IMAGES_FOLDER

    folder_list = []
    for folder in os.listdir(path_photos):
        if os.path.isdir(os.path.join(path_photos, folder)):
            folder_list.append(folder)

    for side_index, side in enumerate(folder_list):
        image_list = []
        for image in os.listdir(path_photos + '/' + side):
            extension = image.split('.')[-1].lower()
            if extension in VALID_IMAGE_EXTENSIONS and not image.startswith('._'):
                image_list.append(path_photos + '/' + side + '/' + image)

        chunk = PhotoScan.app.document.addChunk()
        chunk.label = 'Aligned Side ' + str(side_index + 1)
        chunk.addPhotos(image_list)

    # Save file as .psx as it is requried for netwrok processing.
    save_path = path_druid + '/' + PROCESS_FOLDER + '/'
    save_file = save_path + druid + '.psx'

    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # if not PhotoScan.app.document.save(save_file):
    #     PhotoScan.app.messageBox("Can’t save project")
    PhotoScan.app.document.save(save_file)

    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Aligned"):
            chunks.append(chunk)

    if MODE == 'network':
        tasks = [{'name': 'MatchPhotos',
                  'downscale': int(PhotoScan.HighestAccuracy),
                  'network_distribute': True,
                  'keypoint_limit': '80000',
                  'tiepoint_limit': '0'},
                 {'name': 'AlignCameras',
                  'network_distribute': True},
                 {'name': 'DetectMarkers',
                  'tolerance': '75',
                  'network_distribute': True}]
        start_network_batch_process(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.matchPhotos(accuracy=PhotoScan.HighestAccuracy,
                              generic_preselection=True,
                              reference_preselection=False)
            chunk.alignCameras()
            chunk.detectMarkers(type=PhotoScan.TargetType.CircularTarget12bit,
                                tolerance=75,
                                inverted=False,
                                noparity=False)

#
# Add scale bars.
# Uses encoded markers and known values in meters.
def add_scalebars():
    accuracy = 0.0001

    pairings = ['1_3', '2_4', '49_50', '50_51', '52_53', '53_54',
                '55_56', '57_58', '58_59', '60_61', '61_62', '63_64']

    scale_values = {'49_50': 0.50024, '50_51': 0.50058, '52_53': 0.25007, '53_54': 0.25034,
                    '55_56': 0.25033, '57_58': 0.50027, '58_59': 0.50053, '60_61': 0.25004,
                    '61_62': 0.25033, '63_64': 0.25034, '1_3': 0.12500, '2_4': 0.12500}

    for chunk in PhotoScan.app.document.chunks:
        markers = {}
        for marker in chunk.markers:
            markers.update({marker.label.replace('target ', ''): marker})

        scalebars = {}
        for pair in pairings:
            left, right = pair.split('_')
            if left in markers.keys():
                scalebars[pair] = chunk.addScalebar(markers[left], markers[right])
                scalebars[pair].label = pair
                scalebars[pair].reference.accuracy = accuracy
                scalebars[pair].reference.distance = scale_values[pair]

#
# Creates duplicates of the 'alignment chunks'.
# This allows you to mess up the optimization of the 'alignment chunks'
# without worrying about needing to perform a new alignment.
def setup_optimize():
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith('Aligned'):
            new_chunk = chunk.copy()
            new_chunk.label = chunk.label.replace('Aligned', 'Optimized')
            chunk.enabled = False

def optimize_chunk():
    gradualselection_reconstructionuncertainty_ten()
    delete_and_optimize()
    gradualselection_reconstructionuncertainty_ten()
    delete_and_optimize()

    var = gradual_selection_reprojectionerror()

    while var >= 1:
        var = gradual_selection_reprojectionerror()
        delete_and_optimize()

    if var <= 1.0:
        PhotoScan.app.document.chunk.tiepoint_accuracy = 0.1

    while var >= 0.3:
        var = gradual_selection_reprojectionerror()
        delete_and_optimize_all()

def optimize_chunk_new():
    gradualselection_reconstructionuncertainty()
    delete_and_optimize()
    gradualselection_reconstructionuncertainty()
    delete_and_optimize()

    var = gradual_selection_reprojectionerror()

    while var >= 1:
        var = gradual_selection_reprojectionerror()
        delete_and_optimize()

    if var <= 1.0:
        PhotoScan.app.document.chunk.tiepoint_accuracy = 0.1

    while var >= 0.3:
        var = gradual_selection_reprojectionerror()
        delete_and_optimize_all()

#
# Optimizes sparse cloud an older method.
# In it's current form, this is blindly performed. There are situations where this will
# remove too many points. This doesn't seem to work well when using the turntable method.
def perform_old_optimize():
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Optimized"):
            chunk.enabled = True
            optimize_chunk()

#
# Optimizes sparse cloud using the Tony's method.
# In it's current form, this is blindly performed. There are situations where this will
# remove too many points. This doesn't seem to work well when using the turntable method.
def perform_new_optimize():
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Optimized"):
            chunk.enabled = True
            optimize_chunk_new()

#
# Standard optimization routine.
# Duplicates initial chunks, adds scale bars, blindly performs the
# Chi-method of optimization.
def optimize_old():
    setup_optimize()
    add_scalebars()
    perform_old_optimize()

#
# New optimization routine.
# Duplicates initial chunks, adds scale bars, blindly performs the
# Tony's method of optimization.
def optimize_new():
    setup_optimize()
    add_scalebars()
    perform_new_optimize()

#
# Builds dense cloud, model, texture, creates maks, aligns chunks.
def post_optimize_noalign():
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Optimized"):
            chunks.append(chunk)

    if MODE == 'network':
        tasks = [{'name': 'BuildDenseCloud',
                  'downscale': int(PhotoScan.HighAccuracy),
                  'network_distribute': True},
                 {'name': 'BuildModel',
                  'face_count': 3,
                  'network_distribute': True},
                 {'name': 'BuildUV'},
                 {'name': 'BuildTexture',
                  'texture_count': 1,
                  'texture_size': 4096,
                  'network_distribute': True}]
        start_network_batch_process(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.buildDenseCloud(quality=PhotoScan.MediumQuality)
            chunk.buildModel(surface=PhotoScan.Arbitrary, interpolation=PhotoScan.EnabledInterpolation)
            chunk.buildUV(mapping=PhotoScan.GenericMapping)
            chunk.buildTexture(blending=PhotoScan.MosaicBlending, size=4096)


#
# Builds dense cloud, model, texture, creates maks, aligns chunks.
def post_optimize_n_side():
    chunks = []

    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Optimized"):
            chunks.append(chunk)

    if MODE == 'network':
        tasks = [{'name': 'BuildDenseCloud',
                  'downscale': int(PhotoScan.HighAccuracy),
                  'network_distribute': True},
                 {'name': 'BuildModel',
                  'face_count': 3,
                  'network_distribute': True},
                 #{'name': 'BuildUV'},
                 #{'name': 'BuildTexture',
                 # 'texture_count': 1,
                 # 'texture_size': 4096,
                 # 'network_distribute': True},
                 {'name': 'ImportMasks',
                  'method': 3,
                  'network_distribute': True},
                 {'name': 'AlignChunks',
                  'match_filter_mask': 1,
                  'match_point_limit': 80000,
                  'network_distribute': True}]
        start_network_batch_process(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.buildDenseCloud(quality=PhotoScan.MediumQuality)
            chunk.buildModel(surface=PhotoScan.Arbitrary,
                             interpolation=PhotoScan.EnabledInterpolation)
            #chunk.buildUV(mapping=PhotoScan.GenericMapping)
            #chunk.buildTexture(blending=PhotoScan.MosaicBlending, size=4096)
            chunk.importMasks(path='', source=PhotoScan.MaskSource.MaskSourceModel,
                              operation=PhotoScan.MaskOperation.MaskOperationReplacement)
        PhotoScan.app.document.alignChunks(chunks, chunks[0], method='points', fix_scale=False,
                                           accuracy=PhotoScan.HighAccuracy, preselection=False,
                                           filter_mask=True, point_limit=80000)

#
# Merge chunks and align masked photos.
def merged_and_align():

    if MODE == 'network':
        tasks = [{'name': 'MatchPhotos',
                  'downscale': int(PhotoScan.HigesthAccuracy),
                  'network_distribute': True,
                  'filter_mask': '1',
                  'keypoint_limit': '80000',
                  'tiepoint_limit': '0'},
                 {'name': 'AlignCameras',
                  'network_distribute': True}]
        start_network_batch_process([PhotoScan.app.document.chunk], tasks)
    else:
        chunk = PhotoScan.app.document.chunk
        chunk.matchPhotos(accuracy=PhotoScan.HighAccuracy,
                          generic_preselection=True,
                          reference_preselection=False)
        chunk.alignCameras()

#
#
#
def optimize_merged_sides():
    setup_merged_optimization()

#
# Creates duplicate of the 'merged alignment chunk'.
# This allows you to mess up the optimization of the merged chunk
# without worrying about needing to perform a new alignment.
#
def setup_merged_optimization():
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label == "Merged Chunk":
            chunk_om = chunk.copy()
            chunk_om.label = "Optimized Merged Chunk"
            chunk.enabled = False

#
# Creates final model and textures
def create_dense_and_model():
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label == ("Optimized Merged Chunk"):
            chunks.append(chunk)

    if MODE == 'network':
        tasks = [{'name': 'BuildDenseCloud',
                  'downscale': int(PhotoScan.HighAccuracy),
                  'network_distribute': True},
                 {'name': 'BuildModel',
                  'face_count': 3,
                  'network_distribute': True},
                 {'name': 'BuildUV'},
                 {'name': 'BuildTexture',
                  'texture_count': 1,
                  'texture_size': 4096,
                  'network_distribute': True}]
        start_network_batch_process(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.buildDenseCloud(quality=PhotoScan.MediumQuality)
            chunk.buildModel(surface=PhotoScan.Arbitrary,
                             interpolation=PhotoScan.EnabledInterpolation)
            chunk.buildUV(mapping=PhotoScan.GenericMapping)
            chunk.buildTexture(blending=PhotoScan.MosaicBlending, size=4096)

#
# Deletes selected points and optimizes with some options.
def delete_and_optimize():
    delete_selected_points()
    optimize_partial()

#
# Deletes selected points and optimizes with all options.
def delete_and_optimize_all():
    delete_selected_points()
    optimize_all()

def rescale(val, in_array, out_array):
    return min(out_array) + (val - min(in_array)) * ((max(out_array) - min(out_array)) / (max(in_array) - min(in_array)))

def find_nearest(array,value):
    diff = 91
    idx = 0
    for index in array:
        idiff = abs(value - index)
        if idiff < diff:
            diff = idiff
            idx = index
    return array.index(idx)

#
# Performs a gradual selection using 'reprojection error'
# Blindly selects 10% of the points.
def ramp_gradual_selection_reprojectionerror():
    point_cloud_filter = PhotoScan.PointCloud.Filter()
    point_cloud_filter.init(PhotoScan.app.document.chunk,
                            PhotoScan.PointCloud.Filter.ReconstructionUncertainty)

    points = PhotoScan.app.document.chunk.point_cloud.points.__len__()
    thresh = 1
    thresh_jump = 1
    selected = points

    curve = []

    while selected > 50000:
        selected = 0
        point_cloud_filter.selectPoints(thresh)
        for point in PhotoScan.app.document.chunk.point_cloud.points:
            if point.selected:
                selected += 1
        thresh += thresh_jump
        curve.append(selected)

    angles = []
    for index in range(0, len(curve)-2):
        (distx, disty) = 1.0, abs(rescale(curve[index], curve, range(0, len(curve)-1)))
        angle = math.atan(disty/distx)
        angle *= 180/math.pi
        angles.append(angle)
    elbow = find_nearest(angles, 45)

    return elbow

#
# Performs a gradual selection using 'reprojection error'
# Blindly selects 10% of the points.
def gradual_selection_reprojectionerror():
    point_cloud_filter = PhotoScan.PointCloud.Filter()
    point_cloud_filter.init(PhotoScan.app.document.chunk,
                            PhotoScan.PointCloud.Filter.ReprojectionError)

    target_percent = 10
    points = PhotoScan.app.document.chunk.point_cloud.points.__len__()
    target = int(points / target_percent)
    thresh = 1
    thresh_jump = 1
    selected = points

    high = False
    low = False

    while selected != target:
        selected = 0
        point_cloud_filter.selectPoints(thresh)
        for point in PhotoScan.app.document.chunk.point_cloud.points:
            if point.selected:
                selected += 1
        if selected == target:
            break
        elif selected > target:
            high = True
            thresh += thresh_jump
        else:
            low = True
            thresh -= thresh_jump

        if high & low:
            high = False
            low = False
            thresh_jump = thresh_jump / 10

    return thresh

#
# Performs a gradual selection using 'reconstruction uncertainty'
# Uses the hard-coded value of '10'
def gradualselection_reconstructionuncertainty_ten():
    point_cloud_filter = PhotoScan.PointCloud.Filter()
    point_cloud_filter.init(PhotoScan.app.document.chunk,
                            PhotoScan.PointCloud.Filter.ReconstructionUncertainty)
    point_cloud_filter.selectPoints(10)

#
# Performs a gradual selection using 'reconstruction uncertainty'
# Blindly selects 10% of the points.
def gradualselection_reconstructionuncertainty():
    point_cloud_filter = PhotoScan.PointCloud.Filter()
    point_cloud_filter.init(PhotoScan.app.document.chunk,
                            PhotoScan.PointCloud.Filter.ReconstructionUncertainty)

    target_percent = 10
    points = PhotoScan.app.document.chunk.point_cloud.points.__len__()
    target = int(points / target_percent)
    thresh = 100
    thresh_jump = 100
    selected = points

    high = False
    low = False

    while selected != target:
        selected = 0
        point_cloud_filter.selectPoints(thresh)
        for point in PhotoScan.app.document.chunk.point_cloud.points:
            if point.selected:
                selected += 1
        if selected == target:
            break
        elif selected > target:
            high = True
            thresh += thresh_jump
        else:
            low = True
            thresh -= thresh_jump
        if high & low:
            high = False
            low = False
            thresh_jump = thresh_jump / 10
#
# Deletes selected points
def delete_selected_points():
    PhotoScan.app.document.chunk.point_cloud.removeSelectedPoints()

#
# Exports a PLY and OBJ
def export_models():
    path = re.sub(r"PROCESSING/.*", '', PhotoScan.app.document.path)
    export = path + EXPORT_FOLDER
    ply = export + '/PLY/test.ply'
    obj = export + '/OBJ/test.obj'

    # export obj
    PhotoScan.app.document.chunk.exportModel(obj, False, 6, PhotoScan.ImageFormatPNG, True, False,
                                             False, False, False, False, False, '',
                                             PhotoScan.ModelFormatOBJ)

    # export ply
    PhotoScan.app.document.chunk.exportModel(ply, False, 6, PhotoScan.ImageFormatPNG, True, False,
                                             False, False, False, False, False, '',
                                             PhotoScan.ModelFormatPLY)

# optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True?, fit_b2=True?, fit_k1=True,
#                 fit_k2=True, fit_k3=True, fit_k4=False, fit_p1=True, fit_p2=True, fit_p3=False,
#                 fit_p4=False, fit_shutter=False[, progress])

#
# Optimizes some of the options
# Selections according to the CHI-method
def optimize_partial():
    PhotoScan.app.document.chunk.optimizeCameras(True, True, True, True, True, True, True,
                                                 True, False, True, True, False, False, False)

#
# Optimizes all of the options.
def optimize_all():
    PhotoScan.app.document.chunk.optimizeCameras(True, True, True, True, True, True, True,
                                                 True, True, True, True, True, True, False)

#
# Deletes all chunks other than Algined Side A and B.
# Assumes you did not the 'aligned' sides.
# WARNING: This immediately deletes all other chunks.
def revert_to_clean():
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Aligned"):
            chunk.enabled = True
        else:
            PhotoScan.app.document.remove(chunk)

#
# Moves viewport to face the center of the ROI box.
# This doesn't seem to always work.
def reset_view():
    PhotoScan.app.viewpoint.coo = PhotoScan.app.document.chunk.region.center
    PhotoScan.app.viewpoint.rot = PhotoScan.app.document.chunk.region.rot
    PhotoScan.app.viewpoint.mag = 100

#
# Attempts to create the region ROI. This places the center of the ROI region
# at the midpoint of all of the scale bar markers.
# NOTE: This doesn't actually do anything yet.
def create_roi():
    x_axis, y_axis, z_axis = 0, 0, 0

    for chunk in PhotoScan.app.document.chunks:
        if chunk.label == 'Aligned Side A':
            x_axis, y_axis, z_axis = 0, 0, 0
            num_markers = chunk.markers.__len__()
            for marker in chunk.markers:
                x_axis += marker.position.x
                y_axis += marker.position.y
                z_axis += marker.position.z

            cent_x = x_axis / num_markers
            cent_y = y_axis / num_markers
            cent_z = z_axis / num_markers

            newregion = PhotoScan.Region()
            newregion.size = chunk.region.size
            newregion.rot = chunk.region.rot
            newregion.center = PhotoScan.Vector([cent_x, cent_y, cent_z])
            chunk.region = newregion

#
# Setup Menus
PhotoScan.app.addMenuItem("Automate/Flipflop/1. Import Images", load_images)
PhotoScan.app.addMenuItem("Automate/Flipflop/2a. Old Optimize", optimize_old)
PhotoScan.app.addMenuItem("Automate/Flipflop/2b. New Optimize", optimize_new)
PhotoScan.app.addMenuItem("Automate/Flipflop/3. Create Dense, Model, Mask, Align", post_optimize_n_side)
PhotoScan.app.addMenuItem("Automate/Flipflop/4. Merge Sides and Realign", merged_and_align)
PhotoScan.app.addMenuItem("Automate/Flipflop/5. Optimize Merged", merged_and_align)
PhotoScan.app.addMenuItem("Automate/Flipflop/6. Create Dense, Model, and Texture",
                          create_dense_and_model)
PhotoScan.app.addMenuItem("Automate/Flipflop/7. Export Models", export_models)

PhotoScan.app.addMenuItem("Automate/One Side/1. Import Images", load_images)
PhotoScan.app.addMenuItem("Automate/One Side/2a. Old Optimize", optimize_old)
PhotoScan.app.addMenuItem("Automate/One Side/2b. New Optimize", optimize_new)
PhotoScan.app.addMenuItem("Automate/One Side/3. Create Dense, Model, and Texture",
                          create_dense_and_model)
PhotoScan.app.addMenuItem("Automate/One Side/4. Export Models", export_models)

PhotoScan.app.addMenuItem("Reset/Back to Align", revert_to_clean)
PhotoScan.app.addMenuItem("Reset/Reset View", reset_view)

PhotoScan.app.addMenuItem("Optimize/Cameras/Partial", optimize_partial)
PhotoScan.app.addMenuItem("Optimize/Cameras/All", optimize_all)
PhotoScan.app.addMenuItem("Optimize/Chunk/Sparse Cloud method 1", optimize_chunk)
PhotoScan.app.addMenuItem("Optimize/Chunk/Sparse Cloud method 2", optimize_chunk_new)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10",
                          gradualselection_reconstructionuncertainty_ten)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10%",
                          gradualselection_reconstructionuncertainty)
PhotoScan.app.addMenuItem("Optimize/Selection/Reprojection Error",
                          gradual_selection_reprojectionerror)

PhotoScan.app.addMenuItem("Parts/Add Scale Bars", add_scalebars)

