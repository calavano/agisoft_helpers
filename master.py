"""
Attempts to automate tasks in Agisoft Photoscan
"""
import os
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
UID_FOLDER = ''

def set_uid_folder():
    """Adds UID_FOLDER to global var."""
    global UID_FOLDER
    uid_folder = PhotoScan.app.getExistingDirectory("Specify uid path:")
    uid_folder = uid_folder.replace('\\', '/')
    UID_FOLDER = uid_folder

def queue_network_tasks(chunks, tasks):
    """Adds network tasks to queue."""
    # Force save before creating network task
    PhotoScan.app.document.save()
    network_tasks = []
    network_client = PhotoScan.NetworkClient()
    network_client.connect(SERVER_IP)
    for task_parameters in tasks:
        new_network_task = PhotoScan.NetworkTask()
        for chunk in chunks:
            new_network_task.frames.append((chunk.key, 0))
            new_network_task.name = task_parameters['name']
            for key in task_parameters:
                if key != 'name':
                    new_network_task.params[key] = task_parameters[key]
        network_tasks.append(new_network_task)
    network_save = PhotoScan.app.document.path.replace(SHARED_ROOT, '')
    batch_id = network_client.createBatch(network_save, network_tasks)
    network_client.resumeBatch(batch_id)

def add_images_to_workspace_nside():
    """ Adds images to workspace. Will put arbitrary number of sides into their own chunks.

    Will look for IMAGES_FOLDER in selected folder and create an "Auto: Aligned Side #" chunk
    for all sub-folders.
    """
    global UID_FOLDER
    if not UID_FOLDER:
        uid_folder = PhotoScan.app.getExistingDirectory("Specify uid path:")
        uid_folder = uid_folder.replace('\\', '/')
        UID_FOLDER = uid_folder
    else:
        uid_folder = UID_FOLDER
    path_photos = uid_folder + '/' + IMAGES_FOLDER
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
        chunk.label = 'Auto: Aligned Side ' + str(side_index + 1)
        chunk.addPhotos(image_list)

def save_workspace():
    """Save workspace as a .psx.

    .psx is used instead of .psz to make use of network processing.
    """
    global UID_FOLDER
    if not UID_FOLDER:
        uid_folder = PhotoScan.app.getExistingDirectory("Specify uid path:")
        uid_folder = uid_folder.replace('\\', '/')
        UID_FOLDER = uid_folder
    else:
        uid_folder = UID_FOLDER
    uid = uid_folder.split('/')[-1]
    save_path = uid_folder + '/' + PROCESS_FOLDER + '/'
    save_file = save_path + uid + '.psx'
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    PhotoScan.app.document.save(save_file)

def auto_phase_one():
    """Automatic Step 1: Attempts to align all photos."""
    add_images_to_workspace_nside()
    save_workspace()
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Aligned"):
            chunks.append(chunk)

    if MODE == 'network':
        tasks = [{'name': 'MatchPhotos',
                  'downscale': int(PhotoScan.HighestAccuracy),
                  'network_distribute': True,
                  'keypoint_limit': '50000',
                  'tiepoint_limit': '0'},
                 {'name': 'AlignCameras',
                  'network_distribute': True},
                 {'name': 'DetectMarkers',
                  'tolerance': '75',
                  'network_distribute': True}]
        queue_network_tasks(chunks, tasks)
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

def auto_setup_optimize():
    """Creates copies of Alignment chunks for future optimization."""
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith('Auto: Aligned'):
            new_chunk = chunk.copy()
            new_chunk.label = chunk.label.replace('Aligned', 'Unoptimized')
            chunk.enabled = False

def auto_optimize_sparse_clouds():
    """Optimizes sparse cloud using specified method."""
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Unoptimized"):
            PhotoScan.app.document.chunk = chunk
            optimize_sparse_cloud()
            chunk.label = chunk.label.replace('Unoptimized', 'Optimized')

def auto_optimize_sparse_clouds_new():
    """Optimizes sparse cloud using specified method."""
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Unoptimized"):
            PhotoScan.app.document.chunk = chunk
            optimize_sparse_cloud_new()
            chunk.label = chunk.label.replace('Unoptimized', 'Optimized')

def auto_setup_and_optimize():
    """Sets up optimization, then performs old optimziation method."""
    auto_setup_optimize()
    auto_optimize_sparse_clouds()
    add_scalebars_to_chunk()

def auto_setup_and_optimize_new():
    """Sets up optimization, then performs new optimziation method."""
    auto_setup_optimize()
    auto_optimize_sparse_clouds_new()
    add_scalebars_to_chunk()

def add_scalebars_to_chunk():
    """Adds scalebars to chunk according to hard-coded measurements for encoded markers."""
    accuracy = 0.0001
    pairings = ['1_3', '2_4', '49_50', '50_51', '52_53', '53_54',
                '55_56', '57_58', '58_59', '60_61', '61_62', '63_64']
    scale_values = {'49_50': 0.50024, '50_51': 0.50058, '52_53': 0.25007, '53_54': 0.25034,
                    '55_56': 0.25033, '57_58': 0.50027, '58_59': 0.50053, '60_61': 0.25004,
                    '61_62': 0.25033, '63_64': 0.25034, '1_3': 0.12500, '2_4': 0.12500}
    chunk = PhotoScan.app.document.chunk
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

def optimize_sparse_cloud():
    """Optimizes sparse cloud"""
    reconstructionuncertainty_ten()
    delete_and_optimize()
    reconstructionuncertainty_ten()
    delete_and_optimize()
    var = reprojectionerror()
    while var >= 1:
        var = reprojectionerror()
        delete_and_optimize()
    if var <= 1.0:
        PhotoScan.app.document.chunk.tiepoint_accuracy = 0.1
    while var >= 0.3:
        var = reprojectionerror()
        delete_and_optimize_all()

def optimize_sparse_cloud_new():
    """Optimizes sparse cloud"""
    reconstructionuncertainty()
    delete_and_optimize()
    reconstructionuncertainty()
    delete_and_optimize()
    var = reprojectionerror()
    while var >= 1:
        var = reprojectionerror()
        delete_and_optimize()
    if var <= 1.0:
        PhotoScan.app.document.chunk.tiepoint_accuracy = 0.1
    while var >= 0.3:
        var = reprojectionerror()
        delete_and_optimize_all()

def auto_phase_two_noalign():
    """Build dense cloud, model, and texture."""
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Optimized"):
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
        queue_network_tasks(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.buildDenseCloud(quality=PhotoScan.MediumQuality)
            chunk.buildModel(surface=PhotoScan.Arbitrary,
                             interpolation=PhotoScan.EnabledInterpolation)
            chunk.buildUV(mapping=PhotoScan.GenericMapping)
            chunk.buildTexture(blending=PhotoScan.MosaicBlending, size=4096)

# TODO: Need to fix. Network job failing at BuildDenseCloud.
def auto_phase_two_nside():
    """Build dense cloud, model, create mask from model, align chunks."""
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Optimized"):
            chunks.append(chunk)
    if MODE == 'network':
        tasks = [{'name': 'BuildDenseCloud',
                  'downscale': int(PhotoScan.HighAccuracy),
                  'network_distribute': True},
                 {'name': 'BuildModel',
                  'face_count': 3,
                  'network_distribute': True},
                 {'name': 'ImportMasks',
                  'method': 3,
                  'network_distribute': True},
                 {'name': 'AlignChunks',
                  'match_filter_mask': 1,
                  'match_point_limit': 80000,
                  'network_distribute': True}]
        queue_network_tasks(chunks, tasks)
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

def auto_phase_three():
    """Merge chunks and align masked photos."""
    if MODE == 'network':
        tasks = [{'name': 'MatchPhotos',
                  'downscale': int(PhotoScan.HigesthAccuracy),
                  'network_distribute': True,
                  'filter_mask': '1',
                  'keypoint_limit': '80000',
                  'tiepoint_limit': '0'},
                 {'name': 'AlignCameras',
                  'network_distribute': True}]
        queue_network_tasks([PhotoScan.app.document.chunk], tasks)
    else:
        chunk = PhotoScan.app.document.chunk
        chunk.matchPhotos(accuracy=PhotoScan.HighAccuracy,
                          generic_preselection=True,
                          reference_preselection=False)
        chunk.alignCameras()

def auto_setup_merged_optimization():
    """Creates duplicate of the 'merged alignment chunk' for future optimization."""
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label == "Auto: Merged Chunk":
            chunk_om = chunk.copy()
            chunk_om.label = "Auto: Unoptimized Merged Chunk"
            chunk.enabled = False

def auto_optimize_merged_sides():
    """Perform all steps needed for optimizing merged sides."""
    auto_setup_merged_optimization()
    auto_optimize_sparse_clouds()

def auto_phase_four():
    """Build dense cloud, model, texture for merged chunk."""
    chunks = []
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label == ("Auto: Optimized Merged Chunk"):
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
        queue_network_tasks(chunks, tasks)
    else:
        for chunk in chunks:
            chunk.buildDenseCloud(quality=PhotoScan.MediumQuality)
            chunk.buildModel(surface=PhotoScan.Arbitrary,
                             interpolation=PhotoScan.EnabledInterpolation)
            chunk.buildUV(mapping=PhotoScan.GenericMapping)
            chunk.buildTexture(blending=PhotoScan.MosaicBlending, size=4096)

def delete_and_optimize():
    """Deletes selected points and optimizes with some options."""
    delete_selected_points()
    optimize_partial()

def delete_and_optimize_all():
    """Deletes selected points and optimizes with some options."""
    delete_selected_points()
    optimize_all()

def rescale(val, in_array, out_array):
    """Rescale array of values to arbitrary scale"""
    return min(out_array) \
           + (val - min(in_array)) \
           * ((max(out_array) - min(out_array)) \
           / (max(in_array) - min(in_array)))

def find_nearest(array, value):
    """I forget why I created this."""
    diff = 91
    idx = 0
    for index in array:
        idiff = abs(value - index)
        if idiff < diff:
            diff = idiff
            idx = index
    return array.index(idx)

def ramp_reprojection():
    """Performs a gradual selection using 'reprojection error' with ramp method."""
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

def reprojectionerror():
    """Performs a gradual selection using 'reprojection error'."""
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

def reconstructionuncertainty_ten():
    """Performs a gradual selection using 'reconstruction uncertainty' with 10."""
    point_cloud_filter = PhotoScan.PointCloud.Filter()
    point_cloud_filter.init(PhotoScan.app.document.chunk,
                            PhotoScan.PointCloud.Filter.ReconstructionUncertainty)
    point_cloud_filter.selectPoints(10)

def reconstructionuncertainty():
    """Performs a gradual selection using 'reconstruction uncertainty' with 10%."""
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

def delete_selected_points():
    """Deletes selected points"""
    PhotoScan.app.document.chunk.point_cloud.removeSelectedPoints()

def export_models():
    """Exports a PLY and OBJ"""
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

def optimize_partial():
    """Optimizes some of the options, Selections according to the CHI-method"""
    PhotoScan.app.document.chunk.optimizeCameras(True, True, True, True, True, True, True,
                                                 True, False, True, True, False, False, False)

def optimize_all():
    """Optimizes all of the options, Selections according to the CHI-method"""
    PhotoScan.app.document.chunk.optimizeCameras(True, True, True, True, True, True, True,
                                                 True, True, True, True, True, True, False)

def revert_to_clean():
    """Deletes all chunks other than Algined Side A and B."""
    for chunk in PhotoScan.app.document.chunks:
        if chunk.label.startswith("Auto: Aligned"):
            chunk.enabled = True
        else:
            PhotoScan.app.document.remove(chunk)

def reset_view():
    """Moves viewport to face the center of the ROI box; this doesn't seem to always work."""
    PhotoScan.app.viewpoint.coo = PhotoScan.app.document.chunk.region.center
    PhotoScan.app.viewpoint.rot = PhotoScan.app.document.chunk.region.rot
    PhotoScan.app.viewpoint.mag = 100


def create_roi():
    """ Attempts to create the region ROI. This places the center of the ROI region """
    # """at the midpoint of all of the scale bar markers. """
    # """NOTE: This doesn't actually do anything yet."""
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

def center_bbox_xyz():
    """Centers bounding box to XYZ center."""
    chunk = PhotoScan.app.document.chunk
    transform_matrix = chunk.transform.matrix
    if chunk.crs:
        vect_tm = transform_matrix * PhotoScan.Vector([0, 0, 0, 1])
        vect_tm.size = 3
        locfrm = chunk.crs.localframe(vect_tm)
    else:
        locfrm = PhotoScan.Matrix().diag([1, 1, 1, 1])
    locfrm = locfrm * transform_matrix
    sqrt = math.sqrt(locfrm[0, 0]**2 + locfrm[0, 1]**2 + locfrm[0, 2]**2)
    mat = PhotoScan.Matrix([[locfrm[0, 0], locfrm[0, 1], locfrm[0, 2]],
                            [locfrm[1, 0], locfrm[1, 1], locfrm[1, 2]],
                            [locfrm[2, 0], locfrm[2, 1], locfrm[2, 2]]])
    mat = mat * (1. / sqrt)
    reg = chunk.region
    reg.rot = mat.t()
    chunk.region = reg

#
# Setup Menus
PhotoScan.app.addMenuItem("Automate/Flipflop/1. Import and Align", auto_phase_one)
PhotoScan.app.addMenuItem("Automate/Flipflop/2a. Old Optimize", auto_setup_and_optimize)
PhotoScan.app.addMenuItem("Automate/Flipflop/2b. New Optimize", auto_setup_and_optimize_new)
PhotoScan.app.addMenuItem("Automate/Flipflop/3. Create Dense, Model, Mask, Align",
                          auto_phase_two_nside)
PhotoScan.app.addMenuItem("Automate/Flipflop/4. Merge Sides and Realign", auto_phase_three)
PhotoScan.app.addMenuItem("Automate/Flipflop/5. Optimize Merged", auto_optimize_merged_sides)
PhotoScan.app.addMenuItem("Automate/Flipflop/6. Create Dense, Model, and Texture",
                          auto_phase_four)
PhotoScan.app.addMenuItem("Automate/Flipflop/7. Export Models", export_models)

PhotoScan.app.addMenuItem("Automate/One Side/1. Import and Align", auto_phase_one)
PhotoScan.app.addMenuItem("Automate/One Side/2a. Old Optimize", auto_setup_and_optimize)
PhotoScan.app.addMenuItem("Automate/One Side/2b. New Optimize", auto_setup_and_optimize_new)
PhotoScan.app.addMenuItem("Automate/One Side/3. Create Dense, Model, and Texture",
                          auto_phase_two_noalign)
PhotoScan.app.addMenuItem("Automate/One Side/4. Export Models", export_models)

PhotoScan.app.addMenuItem("Reset/Back to Align", revert_to_clean)
PhotoScan.app.addMenuItem("Reset/Reset View", reset_view)

PhotoScan.app.addMenuItem("Optimize/Cameras/Partial", optimize_partial)
PhotoScan.app.addMenuItem("Optimize/Cameras/All", optimize_all)
PhotoScan.app.addMenuItem("Optimize/Chunk/Sparse Cloud method 1", optimize_sparse_cloud)
PhotoScan.app.addMenuItem("Optimize/Chunk/Sparse Cloud method 2", optimize_sparse_cloud_new)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10",
                          reconstructionuncertainty_ten)
PhotoScan.app.addMenuItem("Optimize/Selection/Reconstruction Uncertainty 10%",
                          reconstructionuncertainty)
PhotoScan.app.addMenuItem("Optimize/Selection/Reprojection Error",
                          reprojectionerror)

PhotoScan.app.addMenuItem("Parts/Add Scale Bars", add_scalebars_to_chunk)
PhotoScan.app.addMenuItem("Parts/Set UID_FOLDER", set_uid_folder)
PhotoScan.app.addMenuItem("Parts/Add Images to Workspace", add_images_to_workspace_nside)
PhotoScan.app.addMenuItem("Parts/Add Optimization Chunks", auto_setup_optimize)
