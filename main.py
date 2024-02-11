#%% import libraries, objects and create Maxwell3d project
import pandas
import pyaedt
from pyaedt import Maxwell3d
from Class import object3d, conductor, magnet, material, phase_winding
app = Maxwell3d(projectname="MasterThesisExample",  solution_type="Transient", non_graphical=False)
app.modeler.model_units = "meter"
app.rename_design("2p6s_0334Hz", save_after_duplicate=True)

#%% generate 2d geometries
def createSurface(object3d) :
    polyline_list = []
    for coordinate in object3d.coordinate2d:
        if len(coordinate) == 2:
            segment_type = 'Line'
        elif len(coordinate) == 3:
            segment_type = 'Arc'
        polyline = app.modeler.create_polyline(coordinate, segment_type=segment_type, name=object3d.name)
        polyline_list.append(polyline)
    unite = app.modeler.unite(polyline_list, keep_originals=False)
    surface = app.modeler.cover_lines(unite)
    return surface

for obj in object3d.obj_inst :
    createSurface(obj)

#%% substract 2d geometries
app.modeler.subtract(app.modeler.get_object_from_name('stator'), app.modeler.get_object_from_name('stator_int'), keep_originals=False)

#%% generate 3d geometries
def createBody(object3d):
    if object3d.coordinate3d != None:
        surface = app.modeler.get_object_from_name(object3d.name)
        polyline = app.modeler.create_polyline(object3d.coordinate3d)
        body = surface.sweep_along_path(polyline)
        return body

for obj in object3d.obj_inst :
    createBody(obj)   

#%% create materials
def createMaterial(material):
    mat = app.materials.add_material(material.name)
    mat.mass_density = material.density
    mat.conductivity = material.conductivity
    if material.nLinear_permeability == None:
        mat.permeability = material.permeability
    else:
        mat.permeability.value = material.nLinear_permeability
    if material.coreloss != None:
        mat.set_electrical_steel_coreloss(**material.coreloss)

for mat in material.mat_inst:
    createMaterial(mat)

#%% assign material to objects
def assignMaterial(object3d):
    if object3d.material != None:
        object = app.modeler.get_object_from_name(object3d.name)
        app.assign_material(object, object3d.material)

for obj in object3d.obj_inst:
    assignMaterial(obj)

#%% create the phases and assign currents
def createPhaseWinding(phase_winding):
    app.assign_winding(coil_terminals=None, winding_type="Current", is_solid=False, current_value=phase_winding.current, parallel_branches=1, name=phase_winding.name)

for ph in phase_winding.ph_inst:
    createPhaseWinding(ph)

#%% create the coil's teminals to assign current
def createCoilTerminal(conductor):
    obj = app.modeler.get_object_from_name(conductor.name)
    if conductor.positive_current == True:
        app.assign_coil(input_object=obj.bottom_face_z, conductor_number=conductor.conductor_number, polarity="Positive", name=conductor.name+"_bottom")
        app.assign_coil(input_object=obj.top_face_z, conductor_number=conductor.conductor_number, polarity="Negative", name=conductor.name+"_top")
    else:
        app.assign_coil(input_object=obj.bottom_face_z, conductor_number=conductor.conductor_number, polarity="Negative", name=conductor.name+"_bottom")
        app.assign_coil(input_object=obj.top_face_z, conductor_number=conductor.conductor_number, polarity="Positive", name=conductor.name+"_top")

for cond in conductor.cond_inst:
    createCoilTerminal(cond)

#%% assign the coils to one of the phase
def assignCoilToPhase(conductor):
    app.add_winding_coils(windingname=conductor.phase_name, coil_names=[conductor.name+"_bottom", conductor.name+"_top"])

for cond in conductor.cond_inst:
    assignCoilToPhase(cond)

#%% set magnetization on the magnets
def assignMagnetization(magnet):
    obj = app.modeler.get_object_from_name(magnet.name)
    mat = app.materials.duplicate_material(material_name=magnet.material, new_name=magnet.name)
    mat.set_magnetic_coercitivity(value=magnet.coercitivity, x=magnet.mag_dir_x, y=magnet.mag_dir_y, z=0)
    app.assign_material(obj, magnet.name)

for mag in magnet.mag_inst:
    assignMagnetization(mag)

#%% create the model's outer region and assign boundary conditions
app.modeler.create_cylinder(cs_axis="Z", position=[0,0,-0.027], radius="0.0252", height = "0.094", numSides="0", name="Region", matname="vacuum")

shaft = app.modeler.get_object_from_name('shaft')
shaft_faces = [shaft.top_face_z, shaft.bottom_face_z]
app.assign_insulating(shaft_faces)

app.assign_rotate_motion(band_object=app.modeler.get_object_from_name('moving_out'), coordinate_system='Global', axis='Z', positive_movement=True, start_position='0deg', angular_velocity='20040')

#%% split model to keep 1 pole only
model_objects = app.modeler.object_list
app.modeler.split(model_objects, plane="YZ", sides="PositiveOnly")
face_to_split = app.modeler.get_faceid_from_position((0, 0, 0), obj_name="Region")
new_obj = app.modeler.create_object_from_face(face_to_split)
obj_splited = app.modeler.split(new_obj, plane="XZ", sides="Both")
master_face = app.modeler.get_object_faces(obj_splited[0])[0]
slave_face = app.modeler.get_object_faces(obj_splited[1])[0]
app.assign_master_slave(master_entity=master_face, slave_entity=slave_face, u_vector_origin_coordinates_master=['0', '0', '0'], u_vector_pos_coordinates_master=['0', '0.1', '0'], u_vector_origin_coordinates_slave=['0', '0', '0'], u_vector_pos_coordinates_slave=['0', '-0.1', '0'], reverse_master=True, reverse_slave=True, same_as_master=False)
app.change_symmetry_multiplier("2")

#%% mesh settings
app.mesh.assign_initial_mesh_from_slider(level=7, method="Auto", usedynamicsurface=True, useflexmesh=False, applycurvilinear=True, usefallback=True, usephi=False, automodelresolution=True)
app.mesh.assign_length_mesh(['stator'], isinside=True, maxlength=0.005, maxel=None, meshop_name="stator")
app.mesh.assign_length_mesh(['magnet_1', 'magnet_2'], isinside=True, maxlength=0.005, maxel=None, meshop_name="magnet")

#%% setup settings
app.set_core_losses(['stator'], value=False) #value is for coreLoss effect on field
app.change_inductance_computation(compute_transient_inductance=True, incremental_matrix=False)
pyaedt.settings.enable_pandas_output=True
setup = app.create_setup(setupname="0334Hz")
setup.props["StopTime"] = "0.002944111776447106s"
setup.props["TimeStep"] = "4.990019960079841e-05s"
setup.props["SaveFieldsType"] = "Every N Steps"
setup.props["N Steps"] = "1"
setup.props["Steps From"] = "0s"
setup.props["Steps To"] = "0.002944111776447106s"
setup.props["OutputPerObjectCoreLoss"] = True
setup.props["OutputPerObjectSolidLoss"] = True
setup.props["OutputError"] = True
setup.props["IsGeneralTransient"] = True
setup.props["IsHalfPeriodicTransient"] = False
setup.props["ScalarPotential"] = "Second Order"
setup.props["SmoothBHCurve"] = False
setup.update()

#%% validate, save and solve the setup
app.validate_simple()
app.save_project()
app.analyze_setup("0334Hz")
app.save_project()

#%% export results and plot torque
app.export_mesh_stats("0334Hz")
result=app.post.get_solution_data("Moving1.Torque")
presult=pandas.concat([result.primary_sweep_values*10**-6,result.data_real()], axis=1, keys=['Time (ms)', 'Torque (Nm)'])
presult.plot(x='Time (ms)',y='Torque (Nm)')
app.release_desktop()