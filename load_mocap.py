import json
import os
import bpy
from bpy import context
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, EnumProperty
from . helper import helper_functions, skeleton_import
import math


class OT_TestOpenFilebrowser(Operator, ImportHelper):

    bl_idname = "test.open_filebrowser"
    bl_label = "Open the file browser (yay)"


    def execute(self, context):
        
        filename, extension = os.path.splitext(self.filepath)
        
        print('real path', os.path.dirname(self.filepath))
        print('Selected file:', self.filepath)
        print('File name:', filename)
        print('File extension:', extension)
        # print('Some Boolean:', self.some_boolean)

        return {'FINISHED'}

class Import_SMPL_easymocap(Operator, ImportHelper):

    bl_idname = "mocap.import_smpl_easymocap"
    bl_label = "Import data"
    bl_description = "Import SMPL EasyMOCAP"



    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )




    def execute(self,context):

        import os
        import json
        import bpy
        from bpy import context
        import math 

        multiplier = context.scene.sk_value_prop.sk_value
        raw_bool = context.scene.sk_value_prop.sk_raw_bool
        debug_bool = context.scene.sk_value_prop.sk_debug_bool
        # reload_skeleton_bool = context.scene.sk_value_prop.sk_reload_skeleton_bool
        limit_rotation_bool = context.scene.sk_value_prop.sk_constraint_limit_rotation_bool

        #========================
        #EASYMOCAP
        #=====================

        import sys
        import bpy
        from os.path import join
        import math
        import numpy as np
        from mathutils import Matrix, Vector, Quaternion, Euler
        import json

        part_match = {'root': 'root', 'bone_00': 'Pelvis', 'bone_01': 'L_Hip', 'bone_02': 'R_Hip',
                    'bone_03': 'Spine1', 'bone_04': 'L_Knee', 'bone_05': 'R_Knee', 'bone_06': 'Spine2',
                    'bone_07': 'L_Ankle', 'bone_08': 'R_Ankle', 'bone_09': 'Spine3', 'bone_10': 'L_Foot',
                    'bone_11': 'R_Foot', 'bone_12': 'Neck', 'bone_13': 'L_Collar', 'bone_14': 'R_Collar',
                    'bone_15': 'Head', 'bone_16': 'L_Shoulder', 'bone_17': 'R_Shoulder', 'bone_18': 'L_Elbow',
                    'bone_19': 'R_Elbow', 'bone_20': 'L_Wrist', 'bone_21': 'R_Wrist', 'bone_22': 'L_Hand', 'bone_23': 'R_Hand'}

        def deg2rad(angle):
            return -np.pi * (angle + 90) / 180.

        def setState0():
            for ob in bpy.data.objects.values():
                ob.select = False
            bpy.context.scene.objects.active = None

        def Rodrigues(rotvec):
            theta = np.linalg.norm(rotvec)
            r = (rotvec/theta).reshape(3, 1) if theta > 0. else rotvec
            cost = np.cos(theta)
            mat = np.asarray([[0, -r[2], r[1]],
                            [r[2], 0, -r[0]],
                            [-r[1], r[0], 0]])
            return(cost*np.eye(3) + (1-cost)*r.dot(r.T) + np.sin(theta)*mat)

        def rodrigues2bshapes(pose):
            rod_rots = np.asarray(pose).reshape(24, 3)
            mat_rots = [Rodrigues(rod_rot) for rod_rot in rod_rots]
            bshapes = np.concatenate([(mat_rot - np.eye(3)).ravel()
                                    for mat_rot in mat_rots[1:]])
            return(mat_rots, bshapes)

        # apply trans pose and shape to character
        def apply_trans_pose_shape(trans, pose, shape, ob, arm_ob, obname, scene, cam_ob, frame=None):
            # transform pose into rotation matrices (for pose) and pose blendshapes
            mrots, bsh = rodrigues2bshapes(pose)

            # set the location of the first bone to the translation parameter
            arm_ob.pose.bones[obname+'_Pelvis'].location = trans
            arm_ob.pose.bones[obname+'_root'].location = trans
            arm_ob.pose.bones[obname +'_root'].keyframe_insert('location', frame=frame)
            # set the pose of each bone to the quaternion specified by pose
            for ibone, mrot in enumerate(mrots):
                bone = arm_ob.pose.bones[obname+'_'+part_match['bone_%02d' % ibone]]
                bone.rotation_quaternion = Matrix(mrot).to_quaternion()
                if frame is not None:
                    bone.keyframe_insert('rotation_quaternion', frame=frame)
                    bone.keyframe_insert('location', frame=frame)

            # apply pose blendshapes
            for ibshape, bshape in enumerate(bsh):
                ob.data.shape_keys.key_blocks['Pose%03d' % ibshape].value = bshape
                if frame is not None:
                    ob.data.shape_keys.key_blocks['Pose%03d' % ibshape].keyframe_insert(
                        'value', index=-1, frame=frame)

            # apply shape blendshapes
            for ibshape, shape_elem in enumerate(shape):
                ob.data.shape_keys.key_blocks['Shape%03d' % ibshape].value = shape_elem
                if frame is not None:
                    ob.data.shape_keys.key_blocks['Shape%03d' % ibshape].keyframe_insert(
                        'value', index=-1, frame=frame)
        import os
        import json

        def read_json(path):
            with open(path) as f:
                data = json.load(f)
            return data
            
        def read_smpl(outname):
            assert os.path.exists(outname), outname
            datas = read_json(outname)
            outputs = []
            for data in datas:
                for key in ['Rh', 'Th', 'poses', 'shapes']:
                    data[key] = np.array(data[key])
                outputs.append(data)
            return outputs

        def merge_params(param_list, share_shape=True):
            output = {}
            for key in ['poses', 'shapes', 'Rh', 'Th', 'expression']:
                if key in param_list[0].keys():
                    output[key] = np.vstack([v[key] for v in param_list])
            if share_shape:
                output['shapes'] = output['shapes'].mean(axis=0, keepdims=True)
            return output

        def load_motions(path):
            from glob import glob
            filenames = sorted(glob(join(path, '*.json')))
            print(filenames)
            motions = {}
            # for filename in filenames[300:900]:
            for filename in filenames:
                infos = read_smpl(filename)
                for data in infos:
                    pid = data['id']
                    if pid not in motions.keys():
                        motions[pid] = []
                    motions[pid].append(data)
            keys = list(motions.keys())
            # BUG: not strictly equal: (Rh, Th, poses) != (Th, (Rh, poses))
            for pid in motions.keys():
                motions[pid] = merge_params(motions[pid])
                motions[pid]['poses'][:, :3] = motions[pid]['Rh']
            return motions
            
        def load_smpl_params(datapath):
            motions = load_motions(datapath)
            return motions

        def init_scene(scene, params, gender='male', angle=0):
            # load fbx model
            # path_fbx=r'D:\MOCAP\EasyMocap_v2\data\smplx\SMPL_maya'
            path_fbx = context.scene.sk_value_prop.sk_smpl_path
            bpy.ops.import_scene.fbx(filepath=join(path_fbx, 'basicModel_%s_lbs_10_207_0_v1.0.2.fbx' % 'm'), axis_forward='-Y', axis_up='-Z', global_scale=100)
            print('success load')
            obname = '%s_avg' % 'm'
            ob = bpy.data.objects[obname]
            ob.data.use_auto_smooth = False  # autosmooth creates artifacts

            bpy.ops.object.select_all(action='DESELECT')

            bpy.ops.object.select_all(action='DESELECT')
            cam_ob = ''

            ob.data.shape_keys.animation_data_clear()
            arm_ob = bpy.data.objects['Armature']
            arm_ob.animation_data_clear()
            
            return(ob, obname, arm_ob, cam_ob)

        params = []
        #path_smpl = r'D:\MOCAP\EasyMocap_v2\1_output\20210423_3\smpl'
        # path_smpl = r'D:\MOCAP\EasyMocap_v2\1_output\20210424_1\smpl'
        path_smpl = self.filepath
        scene = bpy.data.scenes['Scene']

        ob, obname, arm_ob, cam_ob = init_scene(scene, params, 'm')
        #setState0()
        #ob.select = True
        #bpy.context.scene.objects.active = ob
        obj = bpy.context.window.scene.objects[0]
        bpy.context.view_layer.objects.active = ob

        # unblocking both the pose and the blendshape limits
        for k in ob.data.shape_keys.key_blocks.keys():
            bpy.data.shape_keys["Key"].key_blocks[k].slider_min = -10
            bpy.data.shape_keys["Key"].key_blocks[k].slider_max = 10

        #scene.objects.active = arm_ob

        obs = []
        for ob in bpy.context.scene.objects:
            if ob.type == 'ARMATURE':
                obs.append(ob)
        #obs

        armature = obs[len(obs)-1].name

        #bpy.data.objects[armature].select_set(True)
        obs[len(obs)-1].select_set(True)
        view_layer = bpy.context.view_layer
        #Armature_obj = bpy.context.scene.objects[armature]
        Armature_obj = obs[len(obs)-1]
        #view_layer.objects.active = Armature_obj
        view_layer.objects.active = arm_ob



        motions = load_smpl_params(path_smpl)
        for pid, data in motions.items():
            # animation
            arm_ob.animation_data_clear()
        #    cam_ob.animation_data_clear()
            # load smpl params:
            nFrames = data['poses'].shape[0]
            for frame in range(nFrames):
                print(frame)
                scene.frame_set(frame)
                # apply
                trans = data['Th'][frame]
                shape = data['shapes'][0]
                pose = data['poses'][frame]
                apply_trans_pose_shape(Vector(trans), pose, shape, ob,
                                    arm_ob, obname, scene, cam_ob, frame)
        #        scene.update()
                bpy.context.view_layer.update()
        #    bpy.ops.export_anim.bvh(filepath=join(params['out'], '{}.bvh'.format(pid)), frame_start=0, frame_end=nFrames-1)

        return{'FINISHED'}


class Import_Data_easymocap(Operator, ImportHelper):

    bl_idname = "mocap.import_easymocap"
    bl_label = "Import data"
    bl_description = "Import EasyMOCAP"



    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )




    def execute(self,context):

        import os
        import json
        import bpy
        from bpy import context
        import math 

        multiplier = context.scene.sk_value_prop.sk_value
        raw_bool = context.scene.sk_value_prop.sk_raw_bool
        debug_bool = context.scene.sk_value_prop.sk_debug_bool
        # reload_skeleton_bool = context.scene.sk_value_prop.sk_reload_skeleton_bool
        limit_rotation_bool = context.scene.sk_value_prop.sk_constraint_limit_rotation_bool

        #========================
        #EASYMOCAP
        #=====================

        #path = r'D:\MOCAP\EasyMocap-master\Teste_20210321_1_out\keypoints3d'

        
        path = os.path.dirname(self.filepath)
        list_dir = os.listdir(path)
        s_list = sorted(list_dir)

        data = []
        for i in s_list:
            with open(path+ os.sep +i,'r') as f: 
                data.append(json.load(f))
                #json.load(f)
                
        x=0
        y=1
        z=2

        name_points = 'Point'
        
        skeleton_import.create_dots(name_points,25)

        for item in range(len(data)):
            print("frame: ",item)
            for limb in range(len(data[item][0]['keypoints3d'])):
                # print("limb: ",limb)
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[x]=data[item][0]['keypoints3d'][limb][x]
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[y]=data[item][0]['keypoints3d'][limb][y]
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[z]=data[item][0]['keypoints3d'][limb][z]
                #Salva Frame
                bpy.data.objects["Point."+str(1000+limb)[1:]].keyframe_insert(data_path="location", frame=item)


        #===========
        # selectign Scene Collection
        scene_collection = bpy.context.view_layer.layer_collection
        bpy.context.view_layer.active_layer_collection = scene_collection

        bones = [['Bone','Root'],
                ['Bone.001','Spine'],
                ['Bone.002','Neck'],
                ['Bone.003','Face'],
                ['Bone.004','Arm_L'],
                ['Bone.005','Forearm_L'],
                ['Bone.006','Arm_R'],
                ['Bone.007','Forearm_R'],
                ['Bone.008','Thigh_L'],
                ['Bone.009','Leg_L'],
                ['Bone.010','Foot_L'],
                ['Bone.011','Thigh_R'],
                ['Bone.012','Leg_R'],
                ['Bone.013','Foot_R']
                ]

        skeleton_import.create_bones(bones)

        unit = skeleton_import.size_ref_bone('Point.001','Point.008','Point.008')
        unit = unit*multiplier

        spine_multi = context.scene.sk_value_prop.sk_spine_mulitplier
        neck_multi = context.scene.sk_value_prop.sk_neck_mulitplier
        head_multi = context.scene.sk_value_prop.sk_head_mulitplier

        forearm_multi = context.scene.sk_value_prop.sk_forearm_mulitplier
        arm_multi = context.scene.sk_value_prop.sk_arm_mulitplier

        tigh_multi = context.scene.sk_value_prop.sk_tigh_mulitplier
        leg_multi = context.scene.sk_value_prop.sk_leg_mulitplier
        foot_multi = context.scene.sk_value_prop.sk_foot_mulitplier

        root_sz    =unit/10
        spine_sz   =unit*3.5*spine_multi
        neck_sz    =unit*neck_multi
        face_sz    =unit*head_multi
        thigh_sz    =unit*3*tigh_multi
        leg_sz     =unit*2.5*leg_multi
        foot_sz    =unit*foot_multi #inclinado 45 graud pra frente
        arm_sz     =unit*1.5*arm_multi
        forearm_sz =unit*1.5*forearm_multi

        skeleton_import.size_of_bones(unit, root_sz, spine_sz, neck_sz, face_sz, thigh_sz, leg_sz, foot_sz, arm_sz, forearm_sz)



        constraints = [
            ['Root', 'COPY_LOCATION', 'Point.008'],
            ['Root', 'DAMPED_TRACK', 'Point.001'],
            ['Root', 'DAMPED_TRACK', 'Point.012', 'TRACK_X', 0.5],
            ['Root', 'DAMPED_TRACK', 'Point.009', 'TRACK_NEGATIVE_X', 0.5],
            ['Spine', 'DAMPED_TRACK', 'Point.001'],
            ['Spine', 'LIMIT_ROTATION', 'LOCAL'],
            ['Spine', 'LIMIT_ROTATION', 'X', True, -0.349066, 0.349066],
            ['Spine', 'LIMIT_ROTATION', 'Y', True, -0.698132, 0.698132],
            ['Spine', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.174533],
            ['Neck', 'DAMPED_TRACK', 'Point.018'],
            ['Neck', 'LIMIT_ROTATION', 'LOCAL'],
            ['Neck', 'LIMIT_ROTATION', 'X', True, -0.174533, 1.0472],
            ['Neck', 'LIMIT_ROTATION', 'Y', True, -0.523599, 0.523599],
            ['Neck', 'LIMIT_ROTATION', 'Z', True, -0.349066, 0.349066],
            ['Face', 'DAMPED_TRACK', 'Point.000'],
            ['Face', 'LIMIT_ROTATION', 'LOCAL'],
            ['Face', 'LIMIT_ROTATION', 'X', True, -0.174533, 0.872665],
            ['Face', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Face', 'LIMIT_ROTATION', 'Z', True, -0.523599, 0.523599],
            ['Arm_L', 'DAMPED_TRACK', 'Point.006'],
            ['Forearm_L', 'DAMPED_TRACK', 'Point.007'],
            ['Forearm_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_L', 'LIMIT_ROTATION', 'X', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Z', True, -2.53073, -0.191986],
            ['Arm_R', 'DAMPED_TRACK', 'Point.002'],
            ['Forearm_R', 'DAMPED_TRACK', 'Point.003'],
            ['Forearm_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_R', 'LIMIT_ROTATION', 'X', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Y', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Z', True, 0.191986, 2.53073],
            ['Thigh_L', 'DAMPED_TRACK', 'Point.013'],
            ['Thigh_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_L', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_L', 'LIMIT_ROTATION', 'Z', True, -0.785398, 0.174533],
            ['Leg_L', 'DAMPED_TRACK', 'Point.014'],
            ['Leg_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_L', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_L', 'DAMPED_TRACK', 'Point.019'],
            ['Foot_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_L', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Thigh_R', 'DAMPED_TRACK', 'Point.010'],
            ['Thigh_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_R', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_R', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.785398],
            ['Leg_R', 'DAMPED_TRACK', 'Point.011'],
            ['Leg_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_R', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_R', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_R', 'DAMPED_TRACK', 'Point.022'],
            ['Foot_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_R', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_R', 'LIMIT_ROTATION', 'Z', True, 0, 0]
        ]

        # add_constraints(constraints)
        skeleton_import.add_constraints_track_X(constraints, limit_rotation_bool)

        print(len(data))
        bpy.context.scene.frame_end = len(data)

        if debug_bool == False:
            bpy.ops.nla.bake(frame_start=1, frame_end=len(data), visual_keying=True, clear_constraints=True, clear_parents=True, bake_types={'POSE'})
            bpy.ops.object.mode_set(mode='OBJECT')

            skeleton_import.remove_dots(name_points)


            sk_value_prop = context.scene.sk_value_prop
            if raw_bool == True:
                print('raw_bool True - ',raw_bool)

                x_original, y_original, z_original = helper_functions.get_rotations()
                sk_value_prop.sk_root_rot_x = math.degrees(x_original)
                sk_value_prop.sk_root_rot_y = math.degrees(y_original)
                sk_value_prop.sk_root_rot_z = math.degrees(z_original)

                #in this case both original and actual is the same, because there was no alteration on the angle
                x_actual_deg = math.degrees(x_original)
                y_actual_deg = math.degrees(y_original)
                z_actual_deg = math.degrees(z_original)

                sk_value_prop.sk_root_actual_rot_x = x_actual_deg
                sk_value_prop.sk_root_actual_rot_y = y_actual_deg
                sk_value_prop.sk_root_actual_rot_z = z_actual_deg
            else:
                print('raw_bool False - ',raw_bool)
                x_deg, y_deg, z_deg = helper_functions.anim_to_origin()
                #take the information of the rotation to the panel
                print('result x: ',x_deg)
                print('result y: ',y_deg)
                print('result z: ',z_deg)
                sk_value_prop.sk_root_rot_x = x_deg
                sk_value_prop.sk_root_rot_y = y_deg
                sk_value_prop.sk_root_rot_z = z_deg


        return{'FINISHED'}

class Reload_sk_easymocap(Operator):

    bl_idname = "mocap.import_easymocap_reload"
    bl_label = "Reload Skeleton Easymocap"
    bl_description = "Reload SK EasyMOCAP"

    def execute(self,context):

        bpy.ops.object.mode_set(mode='OBJECT')
        multiplier = context.scene.sk_value_prop.sk_value

        unit = skeleton_import.size_ref_bone('Point.001','Point.008','Point.008')
        unit = unit*multiplier

        spine_multi = context.scene.sk_value_prop.sk_spine_mulitplier
        neck_multi = context.scene.sk_value_prop.sk_neck_mulitplier
        head_multi = context.scene.sk_value_prop.sk_head_mulitplier

        forearm_multi = context.scene.sk_value_prop.sk_forearm_mulitplier
        arm_multi = context.scene.sk_value_prop.sk_arm_mulitplier

        tigh_multi = context.scene.sk_value_prop.sk_tigh_mulitplier
        leg_multi = context.scene.sk_value_prop.sk_leg_mulitplier
        foot_multi = context.scene.sk_value_prop.sk_foot_mulitplier

        root_sz    =unit/10
        spine_sz   =unit*3.5*spine_multi
        neck_sz    =unit*neck_multi
        face_sz    =unit*head_multi
        thigh_sz    =unit*3*tigh_multi
        leg_sz     =unit*2.5*leg_multi
        foot_sz    =unit*foot_multi #inclinado 45 graud pra frente
        arm_sz     =unit*1.5*arm_multi
        forearm_sz =unit*1.5*forearm_multi

        skeleton_import.size_of_bones(unit, root_sz, spine_sz, neck_sz, face_sz, thigh_sz, leg_sz, foot_sz, arm_sz, forearm_sz)

        return{'FINISHED'}

class Import_Data_frankmocap(Operator, ImportHelper):
    bl_idname = "mocap.import_frankmocap"
    bl_label = "Import data from Frankmocap"
    bl_description = "Import FrankMocap"


    filename_ext = ".pkl"

    filter_glob: StringProperty(
        default="*.pkl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self,context):

        #"""
        #Frnakmocap
        #==========================
        
        import math
        import bpy
        import os
        import pickle
        import numpy as np
        from bpy import context
        import joblib

        multiplier = context.scene.sk_value_prop.sk_value
        raw_bool = context.scene.sk_value_prop.sk_raw_bool

        def middle_point(p1,p2,p_middle):
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

        def create_dots(name, amount):
            #remove Collection
            if bpy.data.collections.find(name) >= 0:
                collection = bpy.data.collections.get(name)
                #
                for obj in collection.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection)
            #cria os pontos nuima collection chamada Points
            #=====================================================
            collection = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(collection)
            #
            layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
            bpy.context.view_layer.active_layer_collection = layer_collection
            #
            for point in range(amount):
                bpy.ops.mesh.primitive_plane_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
                bpy.ops.mesh.merge(type='CENTER')
                bpy.ops.object.editmode_toggle()
                bpy.context.active_object.name = name+'.'+str(1000+point)[1:]
            #=====================================================

        def distance(point1, point2) -> float:
            #Calculate distance between two points in 3D.
            #    return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
            return math.sqrt((point2.location[0] - point1.location[0]) ** 2 + (point2.location[1] - point1.location[1]) ** 2 + (point2.location[2] - point1.location[2]) ** 2)

        def size_bone(point_name1, point_name2, bone):
            p1 = bpy.data.objects[point_name1]
            p2 = bpy.data.objects[point_name2]
            #edit bones
            if bpy.context.active_object.mode == 'EDIT':
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            else:
                bpy.ops.object.editmode_toggle()
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            bpy.ops.object.editmode_toggle()

        def create_bones(bones_list):
            #===================================
            #creating bones
            #====================================

            bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1)) #cria armature e primeiro bone
            #bpy.ops.object.editmode_toggle()
            #bpy.data.armatures['Armature'].edit_bones.active = bpy.context.object.data.edit_bones['Bone']


            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs


            bpy.ops.armature.select_all(action='DESELECT')
            obs[len(obs)-1].data.edit_bones['Bone'].select_tail=True


            
            bpy.ops.armature.bone_primitive_add()#Spine
            #Neck
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            #Face
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})


            bpy.ops.armature.bone_primitive_add()#Arm_L
            #Forearm_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Arm_R
            #Forearm_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_L
            #Leg_L
            #Foot_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_R
            #Leg_R
            #Foot_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
        
            for i in range(len(bones_list)):
                obs[len(obs)-1].data.edit_bones[bones_list[i][0]].name = bones_list[i][1]


            #Hierarquia
            bpy.context.object.data.edit_bones["Spine"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Arm_L"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Arm_R"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Thigh_L"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Thigh_R"].parent = bpy.context.object.data.edit_bones["Root"]

            bpy.ops.object.editmode_toggle()

        def distance(point1, point2) -> float: 
            #Calculate distance between two points in 3D.
            #return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
            return math.sqrt((point2.location[0] - point1.location[0]) ** 2 + (point2.location[1] - point1.location[1]) ** 2 + (point2.location[2] - point1.location[2]) ** 2)

        def size_bone(point_name1, point_name2, bone):
            p1 = bpy.data.objects[point_name1]
            p2 = bpy.data.objects[point_name2]
            #edit bones
            if bpy.context.active_object.mode == 'EDIT':
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            else:
                bpy.ops.object.editmode_toggle()
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            bpy.ops.object.editmode_toggle()

        def size_ref_bone(p1,p2,p_final):
            from mathutils import Vector
            import bpy

            ## size of the reference bone (spine)
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            # bpy.context.view_layer.objects.active = bpy.data.objects['Point.034']
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            #bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

            x_subtract = abs(obs[0].matrix_world.translation.x - obs[1].matrix_world.translation.x)
            y_subtract = abs(obs[0].matrix_world.translation.y - obs[1].matrix_world.translation.y)
            z_subtract = abs(obs[0].matrix_world.translation.z - obs[1].matrix_world.translation.z)

            max(x_subtract, y_subtract, z_subtract) #maior das medidas
            unit_def = max(x_subtract, y_subtract, z_subtract)/3
            #end of size of reference bone Spine
            return unit_def

        def size_of_bones(root_size, spine_size, neck_size, face_size, thigh_size, leg_size, foot_size, arm_size, forearm_size):
            #==========================================
            #selecting and making the armature Active
            #selecionando armature
            #==========================================
            bpy.ops.object.select_all(action='DESELECT')
            #bpy.ops.armature.select_all(action='DESELECT')

            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            armature = obs[len(obs)-1].name

            #bpy.data.objects[armature].select_set(True)
            obs[len(obs)-1].select_set(True)
            view_layer = bpy.context.view_layer
            #Armature_obj = bpy.context.scene.objects[armature]
            Armature_obj = obs[len(obs)-1]
            view_layer.objects.active = Armature_obj

            #converting to euler rotation
            order = 'XYZ'
            context = bpy.context
            rig_object = context.active_object
            for pb in rig_object.pose.bones:
                pb.rotation_mode = order


            bpy.ops.object.editmode_toggle()

            #changing location
            #resetting
            bpy.context.object.data.edit_bones["Spine"].head.xy=0
            bpy.context.object.data.edit_bones["Neck"].head.xy=0
            bpy.context.object.data.edit_bones["Face"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_L"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_R"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_L"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_L"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_R"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_R"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].head.xy=0
            #tail
            bpy.context.object.data.edit_bones["Face"].tail.xy=0
            bpy.context.object.data.edit_bones["Neck"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].tail.xy=0




            bpy.context.object.data.edit_bones["Root"].length = root_size

            bpy.context.object.data.edit_bones["Spine"].head.z = unit/2
            bpy.context.object.data.edit_bones["Spine"].tail.z = spine_size

            bpy.context.object.data.edit_bones["Neck"].tail.z =  spine_size + neck_size
            bpy.context.object.data.edit_bones["Neck"].tail.y = neck_size/3
            bpy.context.object.data.edit_bones["Face"].tail.z = spine_size + neck_size
            bpy.context.object.data.edit_bones["Face"].tail.y = face_size*-1

            bpy.context.object.data.edit_bones["Arm_L"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Forearm_L"].head.z=  spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].head.x= unit + arm_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.x= unit + arm_size + forearm_size

            bpy.context.object.data.edit_bones["Arm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_R"].head.x= (unit*3/4)*-1
            bpy.context.object.data.edit_bones["Forearm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].head.x= (unit + arm_size) *-1
            bpy.context.object.data.edit_bones["Forearm_R"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].tail.x= (unit + arm_size + forearm_size) *-1

            bpy.context.object.data.edit_bones["Thigh_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Thigh_L"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Leg_L"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.y= foot_sz/2*-1

            bpy.context.object.data.edit_bones["Thigh_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Thigh_R"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.y= foot_size/2*-1

            bpy.ops.object.editmode_toggle()

        def add_constraints_track_X(constraints):
            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            bpy.ops.object.mode_set(mode='POSE')

            for i in range(len(constraints)):
                print('processar: ',constraints[i])
                if  constraints[i][1] == 'COPY_LOCATION' or constraints[i][1] == 'DAMPED_TRACK':
            #        print('in 1 j: ',j,' - name: ',constraints[i][0],' constraint: ',constraints[i][1])
                    obs[len(obs)-1].data.bones.active = obs[len(obs)-1].pose.bones[constraints[i][0]].bone
                    obs[len(obs)-1].pose.bones[constraints[i][0]].bone.select = True
                    #
                    bpy.ops.pose.constraint_add(type=constraints[i][1])
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].target = bpy.data.objects[constraints[i][2]]
                    if constraints[i][1] == 'DAMPED_TRACK' and len(constraints[i])==4:
                        bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].track_axis = constraints[i][3]
                    #
                if constraints[i][1] == 'LIMIT_ROTATION':
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    if constraints[i][2] == 'LOCAL':
                        bpy.ops.pose.constraint_add(type=constraints[i][1])
                        qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                        bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].owner_space = constraints[i][2]
                    if constraints[i][2] == 'X':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_x = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_x  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_x = constraints[i][5]
                    if constraints[i][2] == 'Y':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_y = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_y  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_y = constraints[i][5]
                    if constraints[i][2] == 'Z':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_z = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_z  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_z = constraints[i][5]

        create_dots('Point',49)

        # pkl_path=r'C:\MOCAP\frankmocap\mocap_output\mocap\temp'
        pkl_path = os.path.dirname(self.filepath)
        list_dir = os.listdir(pkl_path)
        s_list = sorted(list_dir)

        len(s_list)

        x=0
        y=1
        z=2
        multi=100
        #armature = 'Armature'


        #exemplo
        file = open(pkl_path+ os.sep +s_list[0],'rb')

        pic = pickle.load(file)
        file.close()

        nppic = np.load(pkl_path+ os.sep +s_list[0], allow_pickle=True)

        for item in range(len(s_list)-1):
            nppic = np.load(pkl_path+ os.sep +s_list[item], allow_pickle=True)
        #    nppic['pred_output_list'][0]['pred_body_joints_img'] #todos os limbs
            print("frame: ",item)
            for limb in range(len(nppic['pred_output_list'][0]['pred_body_joints_img'])):
        #        print("limb: ",limb)
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[z]=nppic['pred_output_list'][0]['pred_body_joints_img'][limb][x]/multi
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[y]=nppic['pred_output_list'][0]['pred_body_joints_img'][limb][y]/multi
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[x]=nppic['pred_output_list'][0]['pred_body_joints_img'][limb][z]/multi
                bpy.data.objects["Point."+str(1000+limb)[1:]].keyframe_insert(data_path="location", frame=item)


        len(nppic['pred_output_list'][0]['pred_body_joints_img'])



        import bpy


        #===========
        # selectign Scene Collection
        scene_collection = bpy.context.view_layer.layer_collection
        bpy.context.view_layer.active_layer_collection = scene_collection

        bones = [['Bone','Root'],
                ['Bone.001','Spine'],
                ['Bone.002','Neck'],
                ['Bone.003','Face'],
                ['Bone.004','Arm_L'],
                ['Bone.005','Forearm_L'],
                ['Bone.006','Arm_R'],
                ['Bone.007','Forearm_R'],
                ['Bone.008','Thigh_L'],
                ['Bone.009','Leg_L'],
                ['Bone.010','Foot_L'],
                ['Bone.011','Thigh_R'],
                ['Bone.012','Leg_R'],
                ['Bone.013','Foot_R']
                ]

        create_bones(bones)

        unit = size_ref_bone('Point.001','Point.008','Point.034')
        unit = unit*multiplier

        root_sz    =unit/10
        spine_sz   =unit*3.5
        neck_sz    =unit
        face_sz    =unit
        thigh_sz    =unit*3
        leg_sz     =unit*2.5
        foot_sz    =unit #inclinado 45 graud pra frente
        arm_sz     =unit*1.5
        forearm_sz =unit*1.5

        size_of_bones(root_sz, spine_sz, neck_sz, face_sz, thigh_sz, leg_sz, foot_sz, arm_sz, forearm_sz)

        constraints = [
            ['Root', 'COPY_LOCATION', 'Point.039'],
            ['Root', 'DAMPED_TRACK', 'Point.037'],
            ['Root', 'DAMPED_TRACK', 'Point.027','TRACK_X'],
            ['Spine', 'DAMPED_TRACK', 'Point.037'],
            ['Spine', 'LIMIT_ROTATION', 'LOCAL'],
            ['Spine', 'LIMIT_ROTATION', 'X', True, -0.349066, 0.349066],
            ['Spine', 'LIMIT_ROTATION', 'Y', True, -0.698132, 0.698132],
            ['Spine', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.174533],
            ['Neck', 'DAMPED_TRACK', 'Point.042'],
            ['Neck', 'LIMIT_ROTATION', 'LOCAL'],
            ['Neck', 'LIMIT_ROTATION', 'X', True, -0.174533, 1.0472],
            ['Neck', 'LIMIT_ROTATION', 'Y', True, -0.523599, 0.523599],
            ['Neck', 'LIMIT_ROTATION', 'Z', True, -0.349066, 0.349066],
            ['Face', 'DAMPED_TRACK', 'Point.044'],
            ['Face', 'LIMIT_ROTATION', 'LOCAL'],
            ['Face', 'LIMIT_ROTATION', 'X', True, -0.174533, 0.872665],
            ['Face', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Face', 'LIMIT_ROTATION', 'Z', True, -0.523599, 0.523599],
            ['Arm_L', 'DAMPED_TRACK', 'Point.032'],
            ['Forearm_L', 'DAMPED_TRACK', 'Point.031'],
            ['Forearm_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_L', 'LIMIT_ROTATION', 'X', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Z', True, -2.53073, -0.191986],
            ['Arm_R', 'DAMPED_TRACK', 'Point.035'],
            ['Forearm_R', 'DAMPED_TRACK', 'Point.036'],
            ['Forearm_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_R', 'LIMIT_ROTATION', 'X', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Y', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Z', True, 0.191986, 2.53073],
            ['Thigh_L', 'DAMPED_TRACK', 'Point.026'],
            ['Thigh_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_L', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_L', 'LIMIT_ROTATION', 'Z', True, -0.785398, 0.174533],
            ['Leg_L', 'DAMPED_TRACK', 'Point.025'],
            ['Leg_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_L', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_L', 'DAMPED_TRACK', 'Point.022'],
            ['Foot_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_L', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Thigh_R', 'DAMPED_TRACK', 'Point.029'],
            ['Thigh_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_R', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_R', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.785398],
            ['Leg_R', 'DAMPED_TRACK', 'Point.030'],
            ['Leg_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_R', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_R', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_R', 'DAMPED_TRACK', 'Point.019'],
            ['Foot_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_R', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_R', 'LIMIT_ROTATION', 'Z', True, 0, 0]
        ]

        add_constraints_track_X(constraints)

        print(len(s_list))
        bpy.context.scene.frame_end = len(s_list)

        bpy.ops.nla.bake(frame_start=1, frame_end=len(s_list), visual_keying=True, clear_constraints=True, clear_parents=True, bake_types={'POSE'})
        bpy.ops.object.mode_set(mode='OBJECT')



        #apagar collection points criada
        collection = bpy.data.collections.get('Point')
        #
        for obj in collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)


        sk_value_prop = context.scene.sk_value_prop
        if raw_bool == True:
            print('raw_bool True - ',raw_bool)

            x_original, y_original, z_original = helper_functions.get_rotations()
            sk_value_prop.sk_root_rot_x = math.degrees(x_original)
            sk_value_prop.sk_root_rot_y = math.degrees(y_original)
            sk_value_prop.sk_root_rot_z = math.degrees(z_original)

            #in this case both original and actual is the same, because there was no alteration on the angle
            x_actual_deg = math.degrees(x_original)
            y_actual_deg = math.degrees(y_original)
            z_actual_deg = math.degrees(z_original)

            sk_value_prop.sk_root_actual_rot_x = x_actual_deg
            sk_value_prop.sk_root_actual_rot_y = y_actual_deg
            sk_value_prop.sk_root_actual_rot_z = z_actual_deg
        else:
            print('raw_bool False - ',raw_bool)
            x_deg, y_deg, z_deg = helper_functions.anim_to_origin()
            #take the information of the rotation to the panel
            print('result x: ',x_deg)
            print('result y: ',y_deg)
            print('result z: ',z_deg)
            sk_value_prop.sk_root_rot_x = x_deg
            sk_value_prop.sk_root_rot_y = y_deg
            sk_value_prop.sk_root_rot_z = z_deg



        return{'FINISHED'}

class Import_Data_vibe(Operator, ImportHelper):
    bl_idname = "mocap.import_vibe"
    bl_label = "Import data from Vibe (needs joblib install)"
    bl_description = "Import Vibe"


    filename_ext = ".pkl"

    filter_glob: StringProperty(
        default="*.pkl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self,context):



        #==========================
        #======VIBE

        #instalar joblib
        #D:\Blender\blender-2.92.0-windows64\2.92\python\bin\python.exe D:\Blender\blender-2.92.0-windows64\2.92\python\lib\site-packages\pip install joblib
        
   
        import math
        import bpy
        import os
        import pickle
        import numpy as np
        from bpy import context
        import joblib

        multiplier = context.scene.sk_value_prop.sk_value
        raw_bool = context.scene.sk_value_prop.sk_raw_bool
        

        def middle_point(p1,p2,p_middle):
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

        def create_dots(name, amount):
            #remove Collection
            if bpy.data.collections.find(name) >= 0:
                collection = bpy.data.collections.get(name)
                #
                for obj in collection.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection)
            #cria os pontos nuima collection chamada Points
            #=====================================================
            collection = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(collection)
            #
            layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
            bpy.context.view_layer.active_layer_collection = layer_collection
            #
            for point in range(amount):
                bpy.ops.mesh.primitive_plane_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
                bpy.ops.mesh.merge(type='CENTER')
                bpy.ops.object.editmode_toggle()
                bpy.context.active_object.name = name+'.'+str(1000+point)[1:]
            #=====================================================
            
        #==============================
        #codes to size the bones
        #==============================

        def distance(point1, point2) -> float: 
            #Calculate distance between two points in 3D.
            #    return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
            return math.sqrt((point2.location[0] - point1.location[0]) ** 2 + (point2.location[1] - point1.location[1]) ** 2 + (point2.location[2] - point1.location[2]) ** 2)

        def size_bone(point_name1, point_name2, bone):
            p1 = bpy.data.objects[point_name1]
            p2 = bpy.data.objects[point_name2]
            #edit bones
            if bpy.context.active_object.mode == 'EDIT':
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            else:
                bpy.ops.object.editmode_toggle()
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            bpy.ops.object.editmode_toggle()

        def create_bones_wo_face(bones_list):
            #===================================
            #creating bones
            #====================================

            bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1)) #cria armature e primeiro bone
            #bpy.ops.object.editmode_toggle()
            #bpy.data.armatures['Armature'].edit_bones.active = bpy.context.object.data.edit_bones['Bone']


            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs


            bpy.ops.armature.select_all(action='DESELECT')
            obs[len(obs)-1].data.edit_bones['Bone'].select_tail=True


            
            bpy.ops.armature.bone_primitive_add()#Spine
            #Neck
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            #Face
            # bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})


            bpy.ops.armature.bone_primitive_add()#Arm_L
            #Forearm_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Arm_R
            #Forearm_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_L
            #Leg_L
            #Foot_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_R
            #Leg_R
            #Foot_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
        
            for i in range(len(bones_list)):
                obs[len(obs)-1].data.edit_bones[bones_list[i][0]].name = bones_list[i][1]


            #Hierarquia
            bpy.context.object.data.edit_bones["Spine"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Arm_L"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Arm_R"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Thigh_L"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Thigh_R"].parent = bpy.context.object.data.edit_bones["Root"]

            bpy.ops.object.editmode_toggle()

        def size_ref_bone(p1,p2,p_final):
            from mathutils import Vector
            import bpy

            ## size of the reference bone (spine)
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            # bpy.context.view_layer.objects.active = bpy.data.objects['Point.034']
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            #bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

            x_subtract = abs(obs[0].matrix_world.translation.x - obs[1].matrix_world.translation.x)
            y_subtract = abs(obs[0].matrix_world.translation.y - obs[1].matrix_world.translation.y)
            z_subtract = abs(obs[0].matrix_world.translation.z - obs[1].matrix_world.translation.z)

            max(x_subtract, y_subtract, z_subtract) #maior das medidas
            unit_def = max(x_subtract, y_subtract, z_subtract)/3
            #end of size of reference bone Spine
            return unit_def

        def size_of_bones(root_size, spine_size, neck_size, face_size, thigh_size, leg_size, foot_size, arm_size, forearm_size):
            #==========================================
            #selecting and making the armature Active
            #selecionando armature
            #==========================================
            bpy.ops.object.select_all(action='DESELECT')
            #bpy.ops.armature.select_all(action='DESELECT')

            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            armature = obs[len(obs)-1].name

            #bpy.data.objects[armature].select_set(True)
            obs[len(obs)-1].select_set(True)
            view_layer = bpy.context.view_layer
            #Armature_obj = bpy.context.scene.objects[armature]
            Armature_obj = obs[len(obs)-1]
            view_layer.objects.active = Armature_obj

            #converting to euler rotation
            order = 'XYZ'
            context = bpy.context
            rig_object = context.active_object
            for pb in rig_object.pose.bones:
                pb.rotation_mode = order


            bpy.ops.object.editmode_toggle()

            #changing location
            #resetting
            bpy.context.object.data.edit_bones["Spine"].head.xy=0
            bpy.context.object.data.edit_bones["Neck"].head.xy=0
            #bpy.context.object.data.edit_bones["Face"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_L"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_R"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_L"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_L"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_R"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_R"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].head.xy=0
            #tail
            #bpy.context.object.data.edit_bones["Face"].tail.xy=0
            bpy.context.object.data.edit_bones["Neck"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].tail.xy=0




            bpy.context.object.data.edit_bones["Root"].length = root_size

            bpy.context.object.data.edit_bones["Spine"].head.z = unit/2
            bpy.context.object.data.edit_bones["Spine"].tail.z = spine_size

            bpy.context.object.data.edit_bones["Neck"].tail.z =  spine_size + neck_size
            bpy.context.object.data.edit_bones["Neck"].tail.y = neck_size/3
            #bpy.context.object.data.edit_bones["Face"].tail.z = spine_size + neck_size
            #bpy.context.object.data.edit_bones["Face"].tail.y = face_size*-1

            bpy.context.object.data.edit_bones["Arm_L"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Forearm_L"].head.z=  spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].head.x= unit + arm_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.x= unit + arm_size + forearm_size

            bpy.context.object.data.edit_bones["Arm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_R"].head.x= (unit*3/4)*-1
            bpy.context.object.data.edit_bones["Forearm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].head.x= (unit + arm_size) *-1
            bpy.context.object.data.edit_bones["Forearm_R"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].tail.x= (unit + arm_size + forearm_size) *-1

            bpy.context.object.data.edit_bones["Thigh_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Thigh_L"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Leg_L"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.y= foot_sz/2*-1

            bpy.context.object.data.edit_bones["Thigh_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Thigh_R"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.y= foot_size/2*-1

            bpy.ops.object.editmode_toggle()

        def add_constraints(constraints):
            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            bpy.ops.object.mode_set(mode='POSE')

            for i in range(len(constraints)):
                print('processar: ',constraints[i])
                if  constraints[i][1] == 'COPY_LOCATION' or constraints[i][1] == 'DAMPED_TRACK':
            #        print('in 1 j: ',j,' - name: ',constraints[i][0],' constraint: ',constraints[i][1])
                    obs[len(obs)-1].data.bones.active = obs[len(obs)-1].pose.bones[constraints[i][0]].bone
                    obs[len(obs)-1].pose.bones[constraints[i][0]].bone.select = True
                    #
                    bpy.ops.pose.constraint_add(type=constraints[i][1])
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].target = bpy.data.objects[constraints[i][2]]
                    #
                if constraints[i][1] == 'LIMIT_ROTATION':
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    if constraints[i][2] == 'LOCAL':
                        bpy.ops.pose.constraint_add(type=constraints[i][1])
                        qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                        bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].owner_space = constraints[i][2]
                    if constraints[i][2] == 'X':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_x = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_x  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_x = constraints[i][5]
                    if constraints[i][2] == 'Y':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_y = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_y  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_y = constraints[i][5]
                    if constraints[i][2] == 'Z':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_z = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_z  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_z = constraints[i][5]

        

        #############################
        ## Start of VIBE import data
        #path = r'D:\MOCAP\EasyMocap-master\demo_test\videos\1.mp4'
        #path = r'D:\Video_editing\running e brack dance para mocap.mp4'
        create_dots('Point',49)



        # pkl_path=r'D:\MOCAP\VIBE\output\sample_video\vibe_output.pkl'
        pkl_path=self.filepath
        pic = joblib.load(pkl_path)

        x=0
        y=1
        z=2

        person_id = context.scene.sk_value_prop.vibe_person_id
        # person_id=1

        for item in range(len(pic[person_id]['pose'])):
            print("frame: ",item)
            final_limbs = int(len(pic[person_id]['pose'][item])/3)
            for limb in range(final_limbs):
                # print("limb: ",limb)
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[x]=pic[person_id]['joints3d'][item][limb][x]
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[y]=pic[person_id]['joints3d'][item][limb][y]
                bpy.data.objects["Point."+str(1000+limb)[1:]].location[z]=pic[person_id]['joints3d'][item][limb][z]
                bpy.data.objects["Point."+str(1000+limb)[1:]].keyframe_insert(data_path="location", frame=item)



        #===========
        # selectign Scene Collection
        scene_collection = bpy.context.view_layer.layer_collection
        bpy.context.view_layer.active_layer_collection = scene_collection

        bones = [['Bone','Root'],
                ['Bone.001','Spine'],
                ['Bone.002','Neck'],
                # ['Bone.003','Face'],
                ['Bone.003','Arm_L'],
                ['Bone.004','Forearm_L'],
                ['Bone.005','Arm_R'],
                ['Bone.006','Forearm_R'],
                ['Bone.007','Thigh_L'],
                ['Bone.008','Leg_L'],
                ['Bone.009','Foot_L'],
                ['Bone.010','Thigh_R'],
                ['Bone.011','Leg_R'],
                ['Bone.012','Foot_R']
                ]

        create_bones_wo_face(bones)

        unit = size_ref_bone('Point.001','Point.008','Point.034')

        unit = unit*multiplier

        root_sz    =unit/10
        spine_sz   =unit*3.5
        neck_sz    =unit
        face_sz    =unit
        thigh_sz    =unit*3
        leg_sz     =unit*2.5
        foot_sz    =unit #inclinado 45 graud pra frente
        arm_sz     =unit*1.5
        forearm_sz =unit*1.5

        size_of_bones(root_sz, spine_sz, neck_sz, face_sz, thigh_sz, leg_sz, foot_sz, arm_sz, forearm_sz)


        constraints = [
            ['Root', 'COPY_LOCATION', 'Point.008'],
            ['Root', 'DAMPED_TRACK', 'Point.001'],
            ['Spine', 'DAMPED_TRACK', 'Point.001'],
            ['Spine', 'LIMIT_ROTATION', 'LOCAL'],
            ['Spine', 'LIMIT_ROTATION', 'X', True, -0.349066, 0.349066],
            ['Spine', 'LIMIT_ROTATION', 'Y', True, -0.698132, 0.698132],
            ['Spine', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.174533],
            ['Neck', 'DAMPED_TRACK', 'Point.000'],
            ['Neck', 'LIMIT_ROTATION', 'LOCAL'],
            ['Neck', 'LIMIT_ROTATION', 'X', True, -0.174533, 1.0472],
            ['Neck', 'LIMIT_ROTATION', 'Y', True, -0.523599, 0.523599],
            ['Neck', 'LIMIT_ROTATION', 'Z', True, -0.349066, 0.349066],
        #    ['Face', 'DAMPED_TRACK', 'Point.000'],
        #    ['Face', 'LIMIT_ROTATION', 'LOCAL'],
        #    ['Face', 'LIMIT_ROTATION', 'X', True, -0.174533, 0.872665],
        #    ['Face', 'LIMIT_ROTATION', 'Y', True, 0, 0],
        #    ['Face', 'LIMIT_ROTATION', 'Z', True, -0.523599, 0.523599],
            ['Arm_L', 'DAMPED_TRACK', 'Point.006'],
            ['Forearm_L', 'DAMPED_TRACK', 'Point.007'],
            ['Forearm_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_L', 'LIMIT_ROTATION', 'X', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Z', True, -2.53073, -0.191986],
            ['Arm_R', 'DAMPED_TRACK', 'Point.003'],
            ['Forearm_R', 'DAMPED_TRACK', 'Point.007'],
            ['Forearm_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_R', 'LIMIT_ROTATION', 'X', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Y', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Z', True, 0.191986, 2.53073],
            ['Thigh_L', 'DAMPED_TRACK', 'Point.013'],
            ['Thigh_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_L', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_L', 'LIMIT_ROTATION', 'Z', True, -0.785398, 0.174533],
            ['Leg_L', 'DAMPED_TRACK', 'Point.014'],
            ['Leg_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_L', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_L', 'DAMPED_TRACK', 'Point.019'],
            ['Foot_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_L', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Thigh_R', 'DAMPED_TRACK', 'Point.010'],
            ['Thigh_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_R', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_R', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.785398],
            ['Leg_R', 'DAMPED_TRACK', 'Point.011'],
            ['Leg_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_R', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_R', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_R', 'DAMPED_TRACK', 'Point.019'],
            ['Foot_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_R', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_R', 'LIMIT_ROTATION', 'Z', True, 0, 0]
        ]

        add_constraints(constraints)


        
        bpy.context.scene.frame_end = len(pic[person_id]['pose'])

        bpy.ops.nla.bake(frame_start=1, frame_end=len(pic[person_id]['pose']), visual_keying=True, clear_constraints=True, clear_parents=True, bake_types={'POSE'})
        bpy.ops.object.mode_set(mode='OBJECT')

        #apagar collection points criada
        collection = bpy.data.collections.get('Point')
        #
        for obj in collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)

        sk_value_prop = context.scene.sk_value_prop
        if raw_bool == True:
            print('raw_bool True - ',raw_bool)

            x_original, y_original, z_original = helper_functions.get_rotations()
            sk_value_prop.sk_root_rot_x = math.degrees(x_original)
            sk_value_prop.sk_root_rot_y = math.degrees(y_original)
            sk_value_prop.sk_root_rot_z = math.degrees(z_original)

            #in this case both original and actual is the same, because there was no alteration on the angle
            x_actual_deg = math.degrees(x_original)
            y_actual_deg = math.degrees(y_original)
            z_actual_deg = math.degrees(z_original)

            sk_value_prop.sk_root_actual_rot_x = x_actual_deg
            sk_value_prop.sk_root_actual_rot_y = y_actual_deg
            sk_value_prop.sk_root_actual_rot_z = z_actual_deg
        else:
            print('raw_bool False - ',raw_bool)
            x_deg, y_deg, z_deg = helper_functions.anim_to_origin()
            #take the information of the rotation to the panel
            print('result x: ',x_deg)
            print('result y: ',y_deg)
            print('result z: ',z_deg)
            sk_value_prop.sk_root_rot_x = x_deg
            sk_value_prop.sk_root_rot_y = y_deg
            sk_value_prop.sk_root_rot_z = z_deg


        
        

        return{'FINISHED'}

class Mediapipe_Pose_estimation(Operator, ImportHelper):
    bl_idname = "mocap.mediapipe_pose"
    bl_label = "Generate Pose using MediaPipe"
    bl_description = "Generate Mocap data with MediaPipe"


    filename_ext = ".mp4"

    filter_glob: StringProperty(
        default="*.mp4",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

        
    def execute(self,context):

        import cv2
        import mediapipe as mp
        import bpy
        import sys
        from mathutils import Vector
        import math

        multiplier = context.scene.sk_value_prop.sk_value
        raw_bool = context.scene.sk_value_prop.sk_raw_bool

        def middle_point(p1,p2,p_middle):
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

        def get_landmarks(vid_name, frame_list):
            mp_drawing = mp.solutions.drawing_utils
            mp_holistic = mp.solutions.holistic
            #
            # For static images:
            holistic = mp_holistic.Holistic(static_image_mode=True)
            for idx, image in enumerate(frame_list):
            #        image_height, image_width, _ = image.shape
                # Convert the BGR image to RGB before processing.
                results = holistic.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            #
            #
                x=0
                y=1
                z=2
                i=0
                print('frame: ',idx)
                try:
                    len(results.pose_landmarks.landmark)
                    for i in range(len(results.pose_landmarks.landmark)):
                        x_pose = results.pose_landmarks.landmark[i].x
                        y_pose = results.pose_landmarks.landmark[i].y
                        z_pose = results.pose_landmarks.landmark[i].z
                        bpy.data.objects["Point."+str(1000+i)[1:]].location[x]=x_pose
                        bpy.data.objects["Point."+str(1000+i)[1:]].location[y]=y_pose
                        bpy.data.objects["Point."+str(1000+i)[1:]].location[z]=z_pose
                        if i == 10:
                            middle_point('Point.009','Point.010','Point.033')
                            bpy.data.objects["Point."+str(1000+33)[1:]].keyframe_insert(data_path="location", frame=idx)
                        if i == 12:
                            middle_point('Point.011','Point.012','Point.034')
                            bpy.data.objects["Point."+str(1000+34)[1:]].keyframe_insert(data_path="location", frame=idx)
                        if i == 24:
                            middle_point('Point.023','Point.024','Point.035')
                            bpy.data.objects["Point."+str(1000+35)[1:]].keyframe_insert(data_path="location", frame=idx)
                        bpy.data.objects["Point."+str(1000+i)[1:]].keyframe_insert(data_path="location", frame=idx)
            #
            #           print('frame: ',idx,' landmark_id: ',i,'x: ', x_pose, ' - y: ',y_pose,' - z: ',z_pose)
                except:
                    print('Error Frame: ',idx)
                    bpy.data.objects["Point."+str(1000+i)[1:]].location[x]=0
                    bpy.data.objects["Point."+str(1000+i)[1:]].location[y]=0
                    bpy.data.objects["Point."+str(1000+i)[1:]].location[z]=0
                    bpy.data.objects["Point."+str(1000+i)[1:]].keyframe_insert(data_path="location", frame=idx)
                    continue
            holistic.close()

        def get_video_frames(file_url):
            vidcap = cv2.VideoCapture(file_url)
            success, image = vidcap.read()
            # array of objects with class 'numpy.ndarray'
            frames = []
            while success:
                frames.append(image)
                success, image = vidcap.read()
            #
            return frames

        def create_dots(name, amount):
            #remove Collection
            if bpy.data.collections.find(name) >= 0:
                collection = bpy.data.collections.get(name)
                #
                for obj in collection.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(collection)
            #cria os pontos nuima collection chamada Points
            #=====================================================
            collection = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(collection)
            #
            layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]
            bpy.context.view_layer.active_layer_collection = layer_collection
            #
            for point in range(amount):
                bpy.ops.mesh.primitive_plane_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
                bpy.ops.mesh.merge(type='CENTER')
                bpy.ops.object.editmode_toggle()
                bpy.context.active_object.name = name+'.'+str(1000+point)[1:]
            #=====================================================

        def create_bones(bones_list):
            #===================================
            #creating bones
            #====================================

            bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1)) #cria armature e primeiro bone
            #bpy.ops.object.editmode_toggle()
            #bpy.data.armatures['Armature'].edit_bones.active = bpy.context.object.data.edit_bones['Bone']


            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs


            bpy.ops.armature.select_all(action='DESELECT')
            obs[len(obs)-1].data.edit_bones['Bone'].select_tail=True


            
            bpy.ops.armature.bone_primitive_add()#Spine
            #Neck
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            #Face
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})


            bpy.ops.armature.bone_primitive_add()#Arm_L
            #Forearm_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Arm_R
            #Forearm_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_L
            #Leg_L
            #Foot_L
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            
            bpy.ops.armature.bone_primitive_add()#Thigh_R
            #Leg_R
            #Foot_R
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0.0, 0.0, 0.1)})
        
            for i in range(len(bones_list)):
                obs[len(obs)-1].data.edit_bones[bones_list[i][0]].name = bones_list[i][1]


            #Hierarquia
            bpy.context.object.data.edit_bones["Spine"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Arm_L"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Arm_R"].parent = bpy.context.object.data.edit_bones["Spine"]
            bpy.context.object.data.edit_bones["Thigh_L"].parent = bpy.context.object.data.edit_bones["Root"]
            bpy.context.object.data.edit_bones["Thigh_R"].parent = bpy.context.object.data.edit_bones["Root"]

            bpy.ops.object.editmode_toggle()

        def distance(point1, point2) -> float: 
            #Calculate distance between two points in 3D.
            #return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
            return math.sqrt((point2.location[0] - point1.location[0]) ** 2 + (point2.location[1] - point1.location[1]) ** 2 + (point2.location[2] - point1.location[2]) ** 2)

        def size_bone(point_name1, point_name2, bone):
            p1 = bpy.data.objects[point_name1]
            p2 = bpy.data.objects[point_name2]
            #edit bones
            if bpy.context.active_object.mode == 'EDIT':
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            else:
                bpy.ops.object.editmode_toggle()
                bpy.context.object.data.edit_bones[bone].length= distance(p1,p2)
            bpy.ops.object.editmode_toggle()

        def size_ref_bone(p1,p2,p_final):
            from mathutils import Vector
            import bpy

            ## size of the reference bone (spine)
            bpy.ops.object.select_all(action='DESELECT')
            bpy.data.objects[p1].select_set(True)
            bpy.data.objects[p2].select_set(True)
            # bpy.context.view_layer.objects.active = bpy.data.objects['Point.034']
            bpy.context.view_layer.objects.active = bpy.data.objects[p2]
            obs = bpy.context.selected_objects
            n = len(obs)
            #    print('n: ',n)
            assert(n)
            #scene.cursor.location = sum([o.matrix_world.translation for o in obs], Vector()) / n
            #bpy.data.objects[p_middle].location = sum([o.matrix_world.translation for o in obs], Vector()) / n

            x_subtract = abs(obs[0].matrix_world.translation.x - obs[1].matrix_world.translation.x)
            y_subtract = abs(obs[0].matrix_world.translation.y - obs[1].matrix_world.translation.y)
            z_subtract = abs(obs[0].matrix_world.translation.z - obs[1].matrix_world.translation.z)

            max(x_subtract, y_subtract, z_subtract) #maior das medidas
            unit_def = max(x_subtract, y_subtract, z_subtract)/3
            #end of size of reference bone Spine
            return unit_def

        def size_of_bones(root_size, spine_size, neck_size, face_size, thigh_size, leg_size, foot_size, arm_size, forearm_size):
            #==========================================
            #selecting and making the armature Active
            #selecionando armature
            #==========================================
            bpy.ops.object.select_all(action='DESELECT')
            #bpy.ops.armature.select_all(action='DESELECT')

            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            armature = obs[len(obs)-1].name

            #bpy.data.objects[armature].select_set(True)
            obs[len(obs)-1].select_set(True)
            view_layer = bpy.context.view_layer
            #Armature_obj = bpy.context.scene.objects[armature]
            Armature_obj = obs[len(obs)-1]
            view_layer.objects.active = Armature_obj

            #converting to euler rotation
            order = 'XYZ'
            context = bpy.context
            rig_object = context.active_object
            for pb in rig_object.pose.bones:
                pb.rotation_mode = order


            bpy.ops.object.editmode_toggle()

            #changing location
            #resetting
            bpy.context.object.data.edit_bones["Spine"].head.xy=0
            bpy.context.object.data.edit_bones["Neck"].head.xy=0
            bpy.context.object.data.edit_bones["Face"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_L"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].head.xy=0

            bpy.context.object.data.edit_bones["Arm_R"].head.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_L"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_L"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].head.xy=0

            bpy.context.object.data.edit_bones["Thigh_R"].head.xy=0
            bpy.context.object.data.edit_bones["Leg_R"].head.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].head.xy=0
            #tail
            bpy.context.object.data.edit_bones["Face"].tail.xy=0
            bpy.context.object.data.edit_bones["Neck"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Forearm_R"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_L"].tail.xy=0
            bpy.context.object.data.edit_bones["Foot_R"].tail.xy=0




            bpy.context.object.data.edit_bones["Root"].length = root_size

            bpy.context.object.data.edit_bones["Spine"].head.z = unit/2
            bpy.context.object.data.edit_bones["Spine"].tail.z = spine_size

            bpy.context.object.data.edit_bones["Neck"].tail.z =  spine_size + neck_size
            bpy.context.object.data.edit_bones["Neck"].tail.y = neck_size/3
            bpy.context.object.data.edit_bones["Face"].tail.z = spine_size + neck_size
            bpy.context.object.data.edit_bones["Face"].tail.y = face_size*-1

            bpy.context.object.data.edit_bones["Arm_L"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Forearm_L"].head.z=  spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].head.x= unit + arm_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_L"].tail.x= unit + arm_size + forearm_size

            bpy.context.object.data.edit_bones["Arm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Arm_R"].head.x= (unit*3/4)*-1
            bpy.context.object.data.edit_bones["Forearm_R"].head.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].head.x= (unit + arm_size) *-1
            bpy.context.object.data.edit_bones["Forearm_R"].tail.z= spine_size
            bpy.context.object.data.edit_bones["Forearm_R"].tail.x= (unit + arm_size + forearm_size) *-1

            bpy.context.object.data.edit_bones["Thigh_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Thigh_L"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Leg_L"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].head.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.x= unit*3/4
            bpy.context.object.data.edit_bones["Foot_L"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_L"].tail.y= foot_sz/2*-1

            bpy.context.object.data.edit_bones["Thigh_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Thigh_R"].head.z= (unit/5)*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Leg_R"].head.z= (unit/5 + thigh_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].head.z= (unit/5 + thigh_size + leg_size)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.x= unit*3/4*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.z= (unit/5 + thigh_size + leg_size + foot_size/2)*-1
            bpy.context.object.data.edit_bones["Foot_R"].tail.y= foot_size/2*-1

            bpy.ops.object.editmode_toggle()

        def add_constraints(constraints):
            obs = []
            for ob in bpy.context.scene.objects:
                if ob.type == 'ARMATURE':
                    obs.append(ob)
            #obs

            bpy.ops.object.mode_set(mode='POSE')

            for i in range(len(constraints)):
                print('processar: ',constraints[i])
                if  constraints[i][1] == 'COPY_LOCATION' or constraints[i][1] == 'DAMPED_TRACK':
            #        print('in 1 j: ',j,' - name: ',constraints[i][0],' constraint: ',constraints[i][1])
                    obs[len(obs)-1].data.bones.active = obs[len(obs)-1].pose.bones[constraints[i][0]].bone
                    obs[len(obs)-1].pose.bones[constraints[i][0]].bone.select = True
                    #
                    bpy.ops.pose.constraint_add(type=constraints[i][1])
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].target = bpy.data.objects[constraints[i][2]]
                    #
                if constraints[i][1] == 'LIMIT_ROTATION':
                    qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                    if constraints[i][2] == 'LOCAL':
                        bpy.ops.pose.constraint_add(type=constraints[i][1])
                        qtd_constraint = len(bpy.context.object.pose.bones[constraints[i][0]].constraints)
                        bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].owner_space = constraints[i][2]
                    if constraints[i][2] == 'X':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_x = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_x  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_x = constraints[i][5]
                    if constraints[i][2] == 'Y':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_y = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_y  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_y = constraints[i][5]
                    if constraints[i][2] == 'Z':
                        if constraints[i][3] == True:
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].use_limit_z = constraints[i][3]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].min_z  = constraints[i][4]
                            bpy.context.object.pose.bones[constraints[i][0]].constraints[qtd_constraint-1].max_z = constraints[i][5]


        #path = r'D:\MOCAP\EasyMocap-master\demo_test\videos\1.mp4'
        # path = r'D:\Video_editing\running e brack dance para mocap.mp4'
        path = self.filepath
        create_dots('Point',36)
        get_landmarks('Name', get_video_frames(path))


        import bpy


        #===========
        # selectign Scene Collection
        scene_collection = bpy.context.view_layer.layer_collection
        bpy.context.view_layer.active_layer_collection = scene_collection

        bones = [['Bone','Root'],
                ['Bone.001','Spine'],
                ['Bone.002','Neck'],
                ['Bone.003','Face'],
                ['Bone.004','Arm_L'],
                ['Bone.005','Forearm_L'],
                ['Bone.006','Arm_R'],
                ['Bone.007','Forearm_R'],
                ['Bone.008','Thigh_L'],
                ['Bone.009','Leg_L'],
                ['Bone.010','Foot_L'],
                ['Bone.011','Thigh_R'],
                ['Bone.012','Leg_R'],
                ['Bone.013','Foot_R']
                ]

        create_bones(bones)
        
        
        unit = size_ref_bone('Point.001','Point.008','Point.034')
        unit = unit*multiplier

        root_sz    =unit/10
        spine_sz   =unit*3.5
        neck_sz    =unit
        face_sz    =unit
        thigh_sz    =unit*3
        leg_sz     =unit*2.5
        foot_sz    =unit #inclinado 45 graud pra frente
        arm_sz     =unit*1.5
        forearm_sz =unit*1.5

        size_of_bones(root_sz, spine_sz, neck_sz, face_sz, thigh_sz, leg_sz, foot_sz, arm_sz, forearm_sz)

        constraints = [
            ['Root', 'COPY_LOCATION', 'Point.035'],
            ['Root', 'DAMPED_TRACK', 'Point.011'],
            ['Spine', 'DAMPED_TRACK', 'Point.011'],
            ['Spine', 'DAMPED_TRACK', 'Point.011'],
            ['Spine', 'LIMIT_ROTATION', 'LOCAL'],
            ['Spine', 'LIMIT_ROTATION', 'X', True, -0.349066, 0.349066],
            ['Spine', 'LIMIT_ROTATION', 'Y', True, -0.698132, 0.698132],
            ['Spine', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.174533],
            ['Neck', 'DAMPED_TRACK', 'Point.033'],
            ['Neck', 'LIMIT_ROTATION', 'LOCAL'],
            ['Neck', 'LIMIT_ROTATION', 'X', True, -0.174533, 1.0472],
            ['Neck', 'LIMIT_ROTATION', 'Y', True, -0.523599, 0.523599],
            ['Neck', 'LIMIT_ROTATION', 'Z', True, -0.349066, 0.349066],
            ['Face', 'DAMPED_TRACK', 'Point.000'],
            ['Face', 'LIMIT_ROTATION', 'LOCAL'],
            ['Face', 'LIMIT_ROTATION', 'X', True, -0.174533, 0.872665],
            ['Face', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Face', 'LIMIT_ROTATION', 'Z', True, -0.523599, 0.523599],
            ['Arm_L', 'DAMPED_TRACK', 'Point.013'],
            ['Forearm_L', 'DAMPED_TRACK', 'Point.015'],
            ['Forearm_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_L', 'LIMIT_ROTATION', 'X', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Forearm_L', 'LIMIT_ROTATION', 'Z', True, -2.53073, -0.191986],
            ['Arm_R', 'DAMPED_TRACK', 'Point.014'],
            ['Forearm_R', 'DAMPED_TRACK', 'Point.016'],
            ['Forearm_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Forearm_R', 'LIMIT_ROTATION', 'X', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Y', False  ],
            ['Forearm_R', 'LIMIT_ROTATION', 'Z', True, 0.191986, 2.53073],
            ['Thigh_L', 'DAMPED_TRACK', 'Point.025'],
            ['Thigh_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_L', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_L', 'LIMIT_ROTATION', 'Z', True, -0.785398, 0.174533],
            ['Leg_L', 'DAMPED_TRACK', 'Point.027'],
            ['Leg_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_L', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_L', 'DAMPED_TRACK', 'Point.031'],
            ['Foot_L', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_L', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_L', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_L', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Thigh_R', 'DAMPED_TRACK', 'Point.026'],
            ['Thigh_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Thigh_R', 'LIMIT_ROTATION', 'X', True, -1.76278, 1.3439],
            ['Thigh_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Thigh_R', 'LIMIT_ROTATION', 'Z', True, -0.174533, 0.785398],
            ['Leg_R', 'DAMPED_TRACK', 'Point.028'],
            ['Leg_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Leg_R', 'LIMIT_ROTATION', 'X', True, 0.0698132, 2.0944],
            ['Leg_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Leg_R', 'LIMIT_ROTATION', 'Z', True, 0, 0],
            ['Foot_R', 'DAMPED_TRACK', 'Point.032'],
            ['Foot_R', 'LIMIT_ROTATION', 'LOCAL'],
            ['Foot_R', 'LIMIT_ROTATION', 'X', True, -0.523599, 0.523599],
            ['Foot_R', 'LIMIT_ROTATION', 'Y', True, 0, 0],
            ['Foot_R', 'LIMIT_ROTATION', 'Z', True, 0, 0]
        ]

        add_constraints(constraints)
        
        frames = len(get_video_frames(path))

        bpy.context.scene.frame_end = frames

        bpy.ops.nla.bake(frame_start=1, frame_end=frames, visual_keying=True, clear_constraints=True, clear_parents=True, bake_types={'POSE'})
        bpy.ops.object.mode_set(mode='OBJECT')



        #apagar collection points criada
        collection = bpy.data.collections.get('Point')
        #
        for obj in collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)

        sk_value_prop = context.scene.sk_value_prop
        if raw_bool == True:
            print('raw_bool True - ',raw_bool)

            x_original, y_original, z_original = helper_functions.get_rotations()
            sk_value_prop.sk_root_rot_x = math.degrees(x_original)
            sk_value_prop.sk_root_rot_y = math.degrees(y_original)
            sk_value_prop.sk_root_rot_z = math.degrees(z_original)

            #in this case both original and actual is the same, because there was no alteration on the angle
            x_actual_deg = math.degrees(x_original)
            y_actual_deg = math.degrees(y_original)
            z_actual_deg = math.degrees(z_original)

            sk_value_prop.sk_root_actual_rot_x = x_actual_deg
            sk_value_prop.sk_root_actual_rot_y = y_actual_deg
            sk_value_prop.sk_root_actual_rot_z = z_actual_deg
        else:
            print('raw_bool False - ',raw_bool)
            x_deg, y_deg, z_deg = helper_functions.anim_to_origin()
            #take the information of the rotation to the panel
            print('result x: ',x_deg)
            print('result y: ',y_deg)
            print('result z: ',z_deg)
            sk_value_prop.sk_root_rot_x = x_deg
            sk_value_prop.sk_root_rot_y = y_deg
            sk_value_prop.sk_root_rot_z = z_deg



        return{'FINISHED'}

class Install_Mediapipe(bpy.types.Operator):
    bl_idname = "install.mediapipe_package"
    bl_label = "Install python Mediapipe Package"
    bl_description = "Install python Mediapipe Package"

    def execute(self,context):

        import subprocess
        import sys
        import os
        
        # path to python.exe
        python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
        
        # upgrade pip
        subprocess.call([python_exe, "-m", "ensurepip"])
        subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
        
        # install required packages
        subprocess.call([python_exe, "-m", "pip", "install", "mediapipe"])

        return{'FINISHED'}

class Install_Joblib(bpy.types.Operator):
    bl_idname = "install.joblib_package"
    bl_label = "Install python JobLib Package"
    bl_description = "Install python JobLib Package"

    def execute(self,context):

        import subprocess
        import sys
        import os
        
        # path to python.exe
        python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
        
        # upgrade pip
        subprocess.call([python_exe, "-m", "ensurepip"])
        subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
        
        # install required packages
        subprocess.call([python_exe, "-m", "pip", "install", "joblib"])

        return{'FINISHED'}

class Convert_axis(Operator):
    bl_idname = "mocap.convert_axis"
    bl_label = "Convert animation axis"
    bl_description = "Convert Axis"

    def execute(self,context):
        
        skvalue = context.scene.sk_value_prop

        print('from: ',skvalue.sk_from_axis,' ','to: ',skvalue.sk_to_axis)
        print('from simplified: ',skvalue.sk_from_axis[-1:],' ','to: ',skvalue.sk_to_axis[-1:])

        helper_functions.rotate_orientation(skvalue.sk_from_axis[-1:],skvalue.sk_to_axis[-1:])
        
        #send actual rotations
        x_actual_deg, y_actual_deg, z_actual_deg = helper_functions.get_rotations()
        skvalue.sk_root_actual_rot_x = math.degrees(x_actual_deg)
        skvalue.sk_root_actual_rot_y = math.degrees(y_actual_deg)
        skvalue.sk_root_actual_rot_z = math.degrees(z_actual_deg)
        return{'FINISHED'}

class Reset_location(Operator):
    bl_idname = "mocap.reset_location"
    bl_label = "Move animation to origin"
    bl_description = "Center Location"
    
    def execute(sel,context):
        helper_functions.reset_loc()
        return{'FINISHED'}

class Reset_rotation(Operator):
    bl_idname = "mocap.reset_rotation"
    bl_label = "Reset rotation, to the Rest rotatio position"
    bl_description = "Reset Rotation"
    
    def execute(sel,context):
        helper_functions.reset_rot()

        sk_value_prop = context.scene.sk_value_prop
        x_actual_deg, y_actual_deg, z_actual_deg = helper_functions.get_rotations()
        sk_value_prop.sk_root_actual_rot_x = math.degrees(x_actual_deg)
        sk_value_prop.sk_root_actual_rot_y = math.degrees(y_actual_deg)
        sk_value_prop.sk_root_actual_rot_z = math.degrees(z_actual_deg)
        return{'FINISHED'}

class Foot_high(Operator):
    bl_idname = "mocap.foot_high"
    bl_label = "Move the animation so the feet touch the floor"
    bl_description = "Move the feet to touch the floor"
    
    def execute(sel,context):
        helper_functions.foot_high()
        return{'FINISHED'}

class Compensate_Rotation(Operator):
    bl_idname = "mocap.compensate_rotation"
    bl_label = "compensate rotation"
    bl_description = "Compensate rotatio acording to value inserted"
    
    def execute(sel,context):
        skvalue = context.scene.sk_value_prop

        helper_functions.compensate_rot(skvalue.sk_rot_compens_x,skvalue.sk_rot_compens_y,skvalue.sk_rot_compens_z)
        return{'FINISHED'}



class Smooth_Bone(Operator):
    bl_idname = "mocap.smooth_bones"
    bl_label = "Smooth Bones"
    bl_description = "Smooth the curves"
    
    def execute(sel,context):
        
        # currently selected 
        o = bpy.context.object
        

        helper_functions.smooth_curves(o)
        return{'FINISHED'}

class Path_SMPL_FBX_File(Operator, ImportHelper):
    bl_idname = "mocap.browse_smpl_file"
    bl_label = "Get the smpl file path"
    bl_description = "Get the smpl file path"


    filename_ext = ".fbx"

    filter_glob: StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self,context):

        # path = self.filepath
        context.scene.sk_value_prop.sk_smpl_path = os.path.dirname(self.filepath)


        return{'FINISHED'}