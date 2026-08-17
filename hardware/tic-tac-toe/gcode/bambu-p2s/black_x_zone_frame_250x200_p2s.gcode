; HEADER_BLOCK_START
; BambuStudio 02.08.00.50
; model printing time: 14m 31s; total estimated time: 21m 33s
; total layer number: 6
; total filament length [mm] : 2537.07
; total filament volume [cm^3] : 6102.36
; total filament weight [g] : 7.44
; filament_density: 1.22
; filament_diameter: 1.75
; max_z_height: 1.20
; filament: 1
; HEADER_BLOCK_END

; CONFIG_BLOCK_START
; accel_to_decel_enable = 0
; accel_to_decel_factor = 50%
; activate_air_filtration = 0
; additional_cooling_fan_speed = 0
; additional_fan_full_speed_layer = 0
; alternate_extra_wall = 0
; apply_scarf_seam_on_circles = 1
; auxiliary_fan = 1
; avoid_crossing_wall_includes_support = 0
; bed_custom_model = 
; bed_custom_texture = 
; bed_exclude_area = 
; bed_temperature_formula = by_first_filament
; before_layer_change_gcode = 
; best_object_pos = 0.5,0.5
; bottom_color_penetration_layers = 3
; bottom_shell_layers = 3
; bottom_shell_thickness = 0
; bottom_surface_density = 100%
; bottom_surface_pattern = monotonic
; bridge_angle = 0
; bridge_flow = 1
; bridge_no_support = 0
; bridge_speed = 50
; brim_object_gap = 0.1
; brim_type = no_brim
; brim_width = 5
; chamber_temperatures = 0
; change_filament_gcode = ;======== P2S filament_change gcode ==========\n;===== 2026/05/15 =====\n\nM620 S[next_filament_id]A\nM204 S9000\n{if toolchange_count > 1 && (z_hop_types[current_filament_id] == 0 || z_hop_types[current_filament_id] == 3)}\nG17\nG2 Z{z_after_toolchange + 0.4} I0.86 J0.86 P1 F10000 ; spiral lift a little from second lift\n{endif}\n\n;nozzle_change_gcode\n\nG1 Z{max_layer_z + 3.0} F1200\n\nM400\nM106 P1 S0\n\n{if toolchange_count == 2}\n; get travel path for change filament\n;M620.1 X[travel_point_1_x] Y[travel_point_1_y] F21000 P0\n;M620.1 X[travel_point_2_x] Y[travel_point_2_y] F21000 P1\n;M620.1 X[travel_point_3_x] Y[travel_point_3_y] F21000 P2\n{endif}\n\n{if ((filament_type[current_filament_id] == \"PLA\") || (filament_type[current_filament_id] == \"PLA-CF\") || (filament_type[current_filament_id] == \"PETG\")) && (nozzle_diameter_at_nozzle_id[current_nozzle_id] == 0.2)}\nM620.10 A0 F74.8347 L[flush_length] H{nozzle_diameter_at_nozzle_id[current_nozzle_id]} T{flush_temperatures[current_filament_id]} P[old_filament_temp] S1\n{else}\nM620.10 A0 F{flush_volumetric_speeds[current_filament_id]/2.4053*60} L[flush_length] H{nozzle_diameter_at_nozzle_id[current_nozzle_id]} T{flush_temperatures[current_filament_id]} P[old_filament_temp] S1\n{endif}\n\n{if ((filament_type[next_filament_id] == \"PLA\") || (filament_type[next_filament_id] == \"PLA-CF\") || (filament_type[next_filament_id] == \"PETG\")) && (nozzle_diameter_at_nozzle_id[next_nozzle_id] == 0.2)}\nM620.10 A1 F74.8347 L[flush_length] H{nozzle_diameter_at_nozzle_id[next_nozzle_id]} T{flush_temperatures[next_filament_id]} P[new_filament_temp] S1\n{else}\nM620.10 A1 F{flush_volumetric_speeds[next_filament_id]/2.4053*60} L[flush_length] H{nozzle_diameter_at_nozzle_id[next_nozzle_id]} T{flush_temperatures[next_filament_id]} P[new_filament_temp] S1\n{endif}\n\nM620.15 C{new_filament_temp - filament_cooling_before_tower[next_filament_id]}\n\n{if long_retraction_when_cut}\nM620.11 P1 L0 I[current_filament_id] E-{retraction_distance_when_cut} F{max((flush_volumetric_speeds[current_filament_id]/2.4053*60), 200)}\n{else}\nM620.11 P0 L0 I[current_filament_id] E0\n{endif}\n\nM620.11 K0 I[current_filament_id] R0\n\n\nT[next_filament_id]\n\n;deretract\n{if filament_type[next_filament_id] == \"TPU\"}\n{else}\n{if filament_type[next_filament_id] == \"PA\"}\n;VG1 E1 F{max(new_filament_e_feedrate, 200)}\n;VG1 E1 F{max(new_filament_e_feedrate/2, 100)}\n{else}\n;VG1 E4 F{max(new_filament_e_feedrate, 200)}\n;VG1 E4 F{max(new_filament_e_feedrate/2, 100)}\n{endif}\n{endif}\n\n; VFLUSH_START\n{if flush_length>41.5}\n;VG1 E41.5 F{min(old_filament_e_feedrate,new_filament_e_feedrate)}\n;VG1 E{flush_length-41.5} F{new_filament_e_feedrate}\n{else}\n;VG1 E{flush_length} F{min(old_filament_e_feedrate,new_filament_e_feedrate)}\n{endif}\nSYNC T{ceil(flush_length / 80) * 5}\n; VFLUSH_END\n\nM1002 set_filament_type:{filament_type[next_filament_id]}\n\nM400\nM83\n{if next_filament_id < 255}\nM620.10 R{retract_length_toolchange[filament_map[next_filament_id]-1]}\nM628 S0\n;VM109 S[new_filament_temp]\n\nM629\nM400\nM983.3 F{filament_max_volumetric_speed[next_filament_id]/2.4} A0.4 R{retract_length_toolchange[filament_map[next_filament_id]-1]}\nM400\nG1 Y247 F30000\nG1 Y217 F18000\n\nG1 Z{max_layer_z + 3.0} F3000\n{if layer_z <= (initial_layer_print_height + 0.001)}\nM204 S[initial_layer_acceleration]\n{else}\nM204 S[travel_acceleration]\n{endif}\n\n{else}\nG1 X[x_after_toolchange] Y[y_after_toolchange] Z[z_after_toolchange] F12000\n{endif}\n\nM621 S[next_filament_id]A\n\nM622.1 S0 ;for prev version, default skip\nM1002 judge_flag powerloss_resume_flag\nM622 J1\nM983.3 F{filament_max_volumetric_speed[next_filament_id]/2.4} A0.4 R{retract_length_toolchange[filament_map[next_filament_id]-1]}\nM400\nG1 Y247 F30000\nG1 Y217 F18000\nG1 Z{max_layer_z + 3.0} F3000\n{if layer_z <= (initial_layer_print_height + 0.001)}\nM204 S[initial_layer_acceleration]\n{else}\nM204 S[travel_acceleration]\n{endif}\nM1002 set_flag powerloss_resume_flag=0\nM623\n\n{if (filament_type[next_filament_id] == \"PLA\") ||  (filament_type[next_filament_id] == \"PETG\")\n ||  (filament_type[next_filament_id] == \"PLA-CF\")  ||  (filament_type[next_filament_id] == \"PETG-CF\")}\nM1015.4 S1 K1 H{nozzle_diameter_at_nozzle_id[next_nozzle_id]} ;enable E air printing detect\n{else}\nM1015.4 S0 K0 H{nozzle_diameter_at_nozzle_id[next_nozzle_id]} ;disable E air printing detect\n{endif}\n\nM620.6 I[next_filament_id] W1 ;enable ams air printing detect\n\nG1 Y256 F18000\n\n{if (overall_chamber_temperature < 40)}\n{if (layer_num + 1 <= close_additional_fan_first_x_layers[next_filament_id])}\n    {if (min_vitrification_temperature <= 50)}\n        M106 P2 S{first_x_layer_fan_speed[next_filament_id]*255.0/100.0 };set first x_layer aux fan\n    {endif}\n{elsif (layer_num + 1 < additional_fan_full_speed_layer[next_filament_id] && additional_fan_full_speed_layer[next_filament_id] > close_additional_fan_first_x_layers[next_filament_id])}\n    {if (min_vitrification_temperature <= 50)}\n        M106 P2 S{(first_x_layer_fan_speed[next_filament_id] + (additional_cooling_fan_speed[next_filament_id] - first_x_layer_fan_speed[next_filament_id]) * (layer_num + 1 - close_additional_fan_first_x_layers[next_filament_id]) / max(additional_fan_full_speed_layer[next_filament_id] - close_additional_fan_first_x_layers[next_filament_id], 1)) * 255.0/100.0}\n    {endif}\n{else}\n    {if (min_vitrification_temperature <= 50)}\n        {if (nozzle_diameter_at_nozzle_id[current_nozzle_id] == 0.2)}\n            M142 P1 R30 S40 U{max_additional_fan/100.0} V1.0 O45; set PLA/TPU ND0.2 chamber autocooling\n        {else}\n            M142 P1 R30 S40 U{max_additional_fan/100.0} V1.0 O45; set PLA/TPU ND0.4 chamber autocooling\n        {endif}\n    {endif}\n{endif}\n{endif}\n\nM622.1 S0\nM1002 judge_flag ventobox_replace_aux1_fan_flag\nM622 J0\n{if (layer_num + 1 <= close_additional_fan_first_x_layers[next_filament_id])}\n    M106 P10 S{first_x_layer_fan_speed[next_filament_id]*255.0/100.0 };set first x_layer left aux fan\n{elsif (layer_num + 1 < additional_fan_full_speed_layer[next_filament_id] && additional_fan_full_speed_layer[next_filament_id] > close_additional_fan_first_x_layers[next_filament_id])}\n    M106 P10 S{(first_x_layer_fan_speed[next_filament_id] + (additional_cooling_fan_speed[next_filament_id] - first_x_layer_fan_speed[next_filament_id]) * (layer_num + 1 - close_additional_fan_first_x_layers[next_filament_id]) / max(additional_fan_full_speed_layer[next_filament_id] - close_additional_fan_first_x_layers[next_filament_id], 1)) * 255.0/100.0}\n{else}\n    M106 P10 S{additional_cooling_fan_speed[next_filament_id]*255.0/100.0};set left aux fan\n{endif}\nM623\n\n;not set fan changing filament
; circle_compensation_manual_offset = 0
; circle_compensation_speed = 200
; close_additional_fan_first_x_layers = 1
; close_fan_the_first_x_layers = 1
; compatible_printers_condition = 
; complete_print_exhaust_fan_speed = 70
; cool_plate_temp = 45
; cool_plate_temp_initial_layer = 45
; cooling_filter_enabled = 0
; cooling_perimeter_transition_distance = 10
; cooling_slowdown_logic = uniform_cooling
; counter_coef_1 = 0
; counter_coef_2 = 0.0003
; counter_coef_3 = 0.0224
; counter_limit_max = 0.03
; counter_limit_min = 0.0224
; counterbore_hole_bridging = none
; curr_bed_type = Textured PEI Plate
; default_acceleration = 10000
; default_filament_colour = ""
; default_filament_profile = "Bambu PLA Basic @BBL P2S"
; default_jerk = 0
; default_nozzle_volume_type = Standard
; default_print_profile = 0.20mm Standard @BBL P2S
; deretraction_speed = 30
; detect_floating_vertical_shell = 1
; detect_narrow_internal_solid_infill = 1
; detect_overhang_wall = 1
; detect_thin_wall = 0
; diameter_limit = 50
; different_settings_to_system = ;;
; draft_shield = disabled
; during_print_exhaust_fan_speed = 70
; elefant_foot_compensation = 0.15
; embedding_wall_into_infill = 0
; enable_arc_fitting = 1
; enable_circle_compensation = 0
; enable_filament_dynamic_map = 0
; enable_height_slowdown = 0
; enable_long_retraction_when_cut = 2
; enable_mixed_color_sublayer = 0
; enable_order_independent_overlap_carving = 0
; enable_overhang_bridge_fan = 1
; enable_overhang_speed = 1
; enable_pre_heating = 0
; enable_pressure_advance = 0
; enable_prime_tower = 1
; enable_support = 0
; enable_support_ironing = 0
; enable_tower_interface_features = 0
; enable_wrapping_detection = 0
; enforce_support_layers = 0
; eng_plate_temp = 55
; eng_plate_temp_initial_layer = 55
; ensure_vertical_shell_thickness = enabled
; exclude_object = 1
; extruder_ams_count = 
; extruder_clearance_dist_to_rod = 36.5
; extruder_clearance_height_to_lid = 141.5
; extruder_clearance_height_to_rod = 32.5
; extruder_clearance_max_radius = 72
; extruder_colour = #018001
; extruder_max_nozzle_count = 1
; extruder_nozzle_stats = 
; extruder_offset = 0x0
; extruder_printable_area = 
; extruder_type = Direct Drive
; extruder_variant_list = "Direct Drive Standard,Direct Drive High Flow"
; fan_cooling_layer_time = 100
; fan_direction = right
; fan_max_speed = 100
; fan_min_speed = 100
; farthest_point_timelapse = 1
; filament_adaptive_volumetric_speed = 0
; filament_adhesiveness_category = 100
; filament_bridge_speed = 25
; filament_change_length = 10
; filament_change_length_nc = 10
; filament_colour = #00AE42
; filament_cooling_before_tower = 10
; filament_cost = 26.99
; filament_density = 1.22
; filament_dev_ams_drying_ams_limitations = 1
; filament_dev_ams_drying_heat_distortion_temperature = 45
; filament_dev_ams_drying_temperature = 45
; filament_dev_ams_drying_time = 12
; filament_dev_chamber_drying_bed_temperature = 70
; filament_dev_chamber_drying_time = 12
; filament_dev_drying_cooling_temperature = 45
; filament_dev_drying_softening_temperature = 50
; filament_diameter = 1.75
; filament_enable_overhang_speed = 1
; filament_end_gcode = "; filament end gcode \n\n"
; filament_extruder_compatibility = 0
; filament_extruder_variant = "Direct Drive Standard"
; filament_flow_ratio = 0.98
; filament_flush_temp = 0
; filament_flush_temp_fast = 0
; filament_flush_volumetric_speed = 0
; filament_ids = GFA50
; filament_is_mixed = 0
; filament_is_support = 0
; filament_map = 1
; filament_map_2 = 0
; filament_map_mode = Auto For Flush
; filament_max_volumetric_speed = 15
; filament_metal_stickiness = None
; filament_minimal_purge_on_wipe_tower = 15
; filament_mixed_components = ""
; filament_mixed_gradient = 0
; filament_mixed_gradient_curve = ""
; filament_mixed_gradient_per_part = 0
; filament_mixed_gradient_range = ""
; filament_mixed_sublayer_ratios = ""
; filament_notes = 
; filament_nozzle_map = 0
; filament_overhang_1_4_speed = 0
; filament_overhang_2_4_speed = 50
; filament_overhang_3_4_speed = 30
; filament_overhang_4_4_speed = 10
; filament_overhang_totally_speed = 10
; filament_pre_cooling_temperature = 0
; filament_pre_cooling_temperature_nc = 0
; filament_preheat_temperature_delta = 10
; filament_prime_volume = 45
; filament_prime_volume_nc = 60
; filament_printable = 3
; filament_ramming_travel_time = 0
; filament_ramming_travel_time_nc = 0
; filament_ramming_volumetric_speed = -1
; filament_ramming_volumetric_speed_nc = -1
; filament_retract_length_nc = 14
; filament_retraction_distances_when_cut = 10
; filament_scarf_gap = 15%
; filament_scarf_height = 10%
; filament_scarf_length = 10
; filament_scarf_seam_type = none
; filament_self_index = 1
; filament_settings_id = "Bambu PLA-CF @BBL P2S 0.4 nozzle"
; filament_shrink = 100%
; filament_soluble = 0
; filament_start_gcode = "; filament start gcode\n"
; filament_tower_interface_pre_extrusion_dist = 10
; filament_tower_interface_pre_extrusion_length = 0
; filament_tower_interface_print_temp = -1
; filament_tower_interface_purge_volume = 20
; filament_tower_ironing_area = 4
; filament_type = PLA-CF
; filament_velocity_adaptation_factor = 1
; filament_vendor = "Bambu Lab"
; filament_volume_map = 0
; filename_format = {input_filename_base}_{filament_type[0]}_{print_time}.gcode
; fill_multiline = 1
; filter_out_gap_fill = 0
; first_layer_print_sequence = 0
; first_x_layer_fan_speed = 40
; first_x_layer_part_fan_speed = 0
; flush_into_infill = 0
; flush_into_objects = 0
; flush_into_support = 1
; flush_multiplier = 1
; flush_multiplier_fast = 1.2
; flush_volumes_matrix = 0,280,280,280,280,0,280,280,280,280,0,280,280,280,280,0
; flush_volumes_vector = 140,140,140,140,140,140,140,140
; full_fan_speed_layer = 0
; fuzzy_skin = none
; fuzzy_skin_first_layer = 0
; fuzzy_skin_mode = displacement
; fuzzy_skin_noise_type = classic
; fuzzy_skin_octaves = 4
; fuzzy_skin_persistence = 0.5
; fuzzy_skin_point_distance = 0.8
; fuzzy_skin_scale = 1
; fuzzy_skin_thickness = 0.3
; gap_infill_speed = 250
; gcode_add_line_number = 0
; gcode_flavor = marlin
; grab_length = 0
; group_algo_with_time = 0
; has_filament_switcher = 0
; has_scarf_joint_seam = 0
; head_wrap_detect_zone = 
; hole_coef_1 = 0
; hole_coef_2 = -0.0028
; hole_coef_3 = 0.1173
; hole_limit_max = 0.1173
; hole_limit_min = 0.048
; hot_plate_temp = 55
; hot_plate_temp_initial_layer = 55
; hotend_cooling_rate = 2
; hotend_heating_rate = 2
; impact_strength_z = 7.8
; independent_support_layer_height = 1
; infill_combination = 0
; infill_direction = 45
; infill_instead_top_bottom_surfaces = 0
; infill_jerk = 9
; infill_lock_depth = 1
; infill_rotate_step = 0
; infill_shift_step = 0.4
; infill_wall_overlap = 15%
; inherits_group = ;;
; initial_layer_acceleration = 500
; initial_layer_flow_ratio = 1
; initial_layer_infill_speed = 105
; initial_layer_jerk = 9
; initial_layer_line_width = 0.5
; initial_layer_print_height = 0.2
; initial_layer_speed = 50
; initial_layer_travel_acceleration = 6000
; inner_wall_acceleration = 0
; inner_wall_jerk = 9
; inner_wall_line_width = 0.45
; inner_wall_speed = 300
; interface_shells = 0
; interlocking_beam = 0
; interlocking_beam_layer_count = 2
; interlocking_beam_width = 0.8
; interlocking_boundary_avoidance = 2
; interlocking_depth = 2
; interlocking_orientation = 22.5
; internal_bridge_support_thickness = 0.8
; internal_solid_infill_line_width = 0.42
; internal_solid_infill_pattern = zig-zag
; internal_solid_infill_speed = 250
; ironing_direction = 45
; ironing_fan_speed = -1
; ironing_flow = 10%
; ironing_inset = 0.21
; ironing_pattern = zig-zag
; ironing_spacing = 0.15
; ironing_speed = 30
; ironing_type = no ironing
; is_infill_first = 0
; layer_change_gcode = ;======== P2S layer_change gcode ==========\n;===== 2026/05/15 ====\n\n{if (layer_num + 1 == 1)}\n{if (overall_chamber_temperature >= 40)}\n    ;not reset filter fan in first layer\n    ;not reset fan\n{else}\n{if (min_vitrification_temperature > 50)}\n    ;not reset filter fan in first layer\n    ;not reset fan\n{endif}\n{endif}\n{endif}\n\n{if (layer_num + 1 <= close_additional_fan_first_x_layers[current_filament_id])}\n{if (overall_chamber_temperature < 40)}\n    {if (min_vitrification_temperature <= 50)}\n        M106 P2 S{first_x_layer_fan_speed[current_filament_id]*255.0/100.0}\n    {endif}\n{endif}\n    M622.1 S0\n    M1002 judge_flag ventobox_replace_aux1_fan_flag\n    M622 J0\n    M106 P10 S{first_x_layer_fan_speed[current_filament_id]*255.0/100.0}; set first x_layer left aux fan\n    M623\n;not reset fan\n{elsif (layer_num + 1 < additional_fan_full_speed_layer[current_filament_id] && additional_fan_full_speed_layer[current_filament_id] > close_additional_fan_first_x_layers[current_filament_id])}\n{if (overall_chamber_temperature < 40)}\n    {if (min_vitrification_temperature <= 50)}\n        M106 P2 S{(first_x_layer_fan_speed[current_filament_id] + (additional_cooling_fan_speed[current_filament_id] - first_x_layer_fan_speed[current_filament_id]) * (layer_num + 1 - close_additional_fan_first_x_layers[current_filament_id]) / max(additional_fan_full_speed_layer[current_filament_id] - close_additional_fan_first_x_layers[current_filament_id], 1)) * 255.0/100.0}\n    {endif}\n{endif}\n    M622.1 S0\n    M1002 judge_flag ventobox_replace_aux1_fan_flag\n    M622 J0\n    M106 P10 S{(first_x_layer_fan_speed[current_filament_id] + (additional_cooling_fan_speed[current_filament_id] - first_x_layer_fan_speed[current_filament_id]) * (layer_num + 1 - close_additional_fan_first_x_layers[current_filament_id]) / max(additional_fan_full_speed_layer[current_filament_id] - close_additional_fan_first_x_layers[current_filament_id], 1)) * 255.0/100.0}\n    M623\n;not reset fan\n{elsif (layer_num + 1 == max(close_additional_fan_first_x_layers[current_filament_id] + 1, additional_fan_full_speed_layer[current_filament_id]))}\n{if (overall_chamber_temperature < 40)}\n    ;updata chamber autocooling in Xth layer\n    {if (min_vitrification_temperature <= 50)}\n        {if (nozzle_diameter_at_nozzle_id[current_nozzle_id] == 0.2)}\n            M142 P1 R30 S40 U{max_additional_fan/100.0} V1.0 O45; set PLA/TPU ND0.2 chamber autocooling\n        {else}\n            M142 P1 R30 S40 U{max_additional_fan/100.0} V1.0 O45; set PLA/TPU ND0.4 chamber autocooling\n        {endif}\n    {else}\n            ;not reset filter fan in Xth layer\n    {endif}\n{else}\n        ;not reset filter fan in Xth layer\n{endif}\n    M622.1 S0\n    M1002 judge_flag ventobox_replace_aux1_fan_flag\n    M622 J0\n    M106 P10 S{additional_cooling_fan_speed[current_filament_id]*255.0/100.0}; set left aux fan\n    M623\n;not reset fan\n{endif}\n\n; update layer progress\nM73 L{layer_num+1}\nM991 S0 P{layer_num} ;notify layer change\n\n
; layer_height = 0.2
; line_width = 0.42
; locked_skeleton_infill_pattern = zigzag
; locked_skin_infill_pattern = crosszag
; long_retractions_when_cut = 0
; long_retractions_when_ec = 0
; machine_bed_mass_Y = 0
; machine_end_gcode = ;======== P2S end gcode ==========\n;===== 2026/05/18 =====\nM400 ; wait for buffer to clear\nG92 E0 ; zero the extruder\nM211 Z1\n\nG90\nG1 Z{max_layer_z + 0.4} F900 ; lower z a little\nM1002 judge_flag timelapse_record_flag\nM622 J1\n    G150.3\n    M400 ; wait all motion done\n    M991 S0 P-1 ;end smooth timelapse at safe pos\n    M400 S5 ;wait for last picture to be taken\nM623  ;end of \"timelapse_record_flag\n\nG90\nG1 Z{max_layer_z + 10} F900 ; lower z a little\n\nM140 S0 ; turn off bed\nM106 S0 ; turn off fan\nM106 P2 S0 ; turn off remote part cooling fan\nM106 P3 S0 ; turn off chamber cooling fan\nM106 P10 S0 ; turn off left aux fan\n\n; pull back filament to AMS\nM620 S65535\nT65535\nG150.1 F8000\nM621 S65535\n\nG150.3\nM104 S0 ; turn off hotend\nM400 ; wait all motion done\nM17 S\nM17 Z0.4 ; lower z motor current to reduce impact if there is something in the bottom\n{if (80.0 - max_layer_z/2) > 0}\n    {if (max_layer_z + 80.0 - max_layer_z/2) < 256}\n        G1 Z{max_layer_z + 80.0 - max_layer_z/2} F600\n        G1 Z{max_layer_z + 78.0 - max_layer_z/2}\n    {else}\n        G1 Z256 F600\n        G1 Z256\n    {endif}\n{else}\n    {if (max_layer_z + 4.0) < 256}\n        G1 Z{max_layer_z + 4.0} F600\n        G1 Z{max_layer_z + 2.0}\n    {else}\n        G1 Z256 F600\n        G1 Z256\n    {endif}\n{endif}\nM400 P100\nM17 R ; restore z current\n\n\nM220 S100  ; Reset feedrate magnitude\nM201.2 K1.0 ; Reset acc magnitude\nM73.2 R1.0 ;Reset left time magnitude\nM1002 set_gcode_claim_speed_level : 0\n\nM1015.3 S0 ;disable clog detect\nM1015.4 S0 K0 ;disable air printing detect\n\n;=====printer finish air purification=========\nM622.1 S0\nM1002 judge_flag print_finish_air_filt_flag\n\nM622 J1\nM1002 gcode_claim_action : 66\nM145 P1\nM106 P2 S255\nM400 S180\nM106 P2 S0\nM623\n\nM622 J2\nM1002 gcode_claim_action : 66\nM145 P0\nM106 P3 S255\nM400 S180\nM106 P3 S0\nM623\n;=====printer finish air purification=========\n\n;=====printer finish  sound=========\nM17\nM400 S1\nM1006 S1\nM1006 A53 B10 L50 C53 D10 M50 E53 F10 N50 \nM1006 A57 B10 L50 C57 D10 M50 E57 F10 N50 \nM1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 \nM1006 A53 B10 L50 C53 D10 M50 E53 F10 N50 \nM1006 A57 B10 L50 C57 D10 M50 E57 F10 N50 \nM1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 \nM1006 A48 B10 L50 C48 D10 M50 E48 F10 N50 \nM1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 \nM1006 A60 B10 L50 C60 D10 M50 E60 F10 N50 \nM1006 W\n;=====printer finish  sound=========\nM400\nM18\n
; machine_hotend_change_time = 0
; machine_load_filament_time = 26
; machine_max_acceleration_e = 5000,5000
; machine_max_acceleration_extruding = 20000,20000
; machine_max_acceleration_retracting = 5000,5000
; machine_max_acceleration_travel = 10000,10000
; machine_max_acceleration_x = 20000,20000
; machine_max_acceleration_y = 20000,20000
; machine_max_acceleration_z = 500,500
; machine_max_force_Y = 0
; machine_max_jerk_e = 2.5,2.5
; machine_max_jerk_x = 9,9
; machine_max_jerk_y = 9,9
; machine_max_jerk_z = 3,3
; machine_max_printed_mass = 0
; machine_max_speed_e = 30,30
; machine_max_speed_x = 600,600
; machine_max_speed_y = 600,600
; machine_max_speed_z = 20,20
; machine_min_extruding_rate = 0
; machine_min_travel_rate = 0
; machine_pause_gcode = M400 U1
; machine_prepare_compensation_time = 370
; machine_start_gcode = ;M1002 set_flag extrude_cali_flag=1\n;M1002 set_flag g29_before_print_flag=1\n;M1002 set_flag auto_cali_toolhead_offset_flag=1\n;M1002 set_flag build_plate_detect_flag=1\n\n;======== P2S start gcode==========\n;===== 2026/05/18 =====\n\n  M140 S[bed_temperature_initial_layer_single] ; heat heatbed first\n  M993 A0 B0 C0 ; nozzle cam detection not allowed.\n  M400\n\n;=====printer start sound ===================\nM17\nM400 S1\nM1006 S1\nM1006 A53 B9 L50 C53 D9 M50 E53 F9 N50\nM1006 A56 B9 L50 C56 D9 M50 E56 F9 N50\nM1006 A61 B9 L50 C61 D9 M50 E61 F9 N50\nM1006 A53 B9 L50 C53 D9 M50 E53 F9 N50\nM1006 A56 B9 L50 C56 D9 M50 E56 F9 N50\nM1006 A61 B18 L50 C61 D18 M50 E61 F18 N50\nM1006 W\n;=====printer start sound ===================\n\n  M620 M ;enable remap\n  G389\n\n;===== avoid end stop =================\n  G91\n  G380 S2 Z22 F1200\n  G380 S2 Z-12 F1200\n  G90\n;===== avoid end stop =================\n\n;===== reset machine status =================\n  M204 S10000\n  M630 S0 P1\n  G90\n  M17 D ; reset motor current to default\n  M960 S5 P1 ; turn on logo lamp\n  G90\n  M220 S100 ;Reset Feedrate\n  M1002 set_gcode_claim_speed_level: 5\n  M221 S100 ;Reset Flowrate\n  M73.2   R1.0 ;Reset left time magnitude\n  G29.1 Z{+0.0} ; clear z-trim value first\n  M983.1 M1\n  M982.2 S1 ; turn on cog noise reduction\n  M983.4 S0\n;===== reset machine status =================\n\n;==== set airduct mode ====\n;==== if Chamber Cooling is necessary ====\n{if (overall_chamber_temperature >= 40)}\nM145 P1 ; set airduct mode to heating mode for heating\nM106 P2 S255 ; turn on filter fan\nM622.1 S0\nM1002 judge_flag ventobox_replace_aux1_fan_flag\nM622 J0\nM106 P10 S0 ; turn off left aux fan\nM623\n{else}\n{if (min_vitrification_temperature <= 50)}\nM145 P0 ; set airduct mode to cooling mode for cooling\nM106 P2 S255 ; turn on auxiliary fan for cooling\nM106 P3 S127 ; turn on chamber fan for cooling\nM1002 gcode_claim_action : 29\nM191 S0 ; wait for chamber temp\nM106 P2 S102 ; turn on chamber cooling fan\nM622.1 S0\nM1002 judge_flag ventobox_replace_aux1_fan_flag\nM622 J0\nM106 P10 S0 ; turn off left aux fan\nM623\nM142 P6 R30 S40 U0.3 V0.8 ; set PETG exhaust chamber autocooling\n{else}\nM145 P1 ; set airduct mode to heating mode for heating\nM106 P2 S127 ; turn on 50% filter fan\nM142 P6 R30 S40 U0.3 V0.8 ; set PLA/TPU exhaust chamber autocooling\n{endif}\n{endif}\n;==== set airduct mode ====\n\n;===== start to heat heatbed & hotend==========\n  M1002 gcode_claim_action : 2\n  M1002 set_filament_type:{filament_type[initial_no_support_filament_id]}\n  M104 S140 A\n\n  G29.2 S0 ; avoid invalid abl data\n\n;===== first homing start =====\n  M1002 gcode_claim_action : 13\n  G28 X T300\n  G150.1 F8000 ; wipe mouth to avoid filament stick to heatbed\n  G150.3\n  M972 S24 P0\n  M972 S26 P0 C0\n  M972 S42 P0 T5000\n  G150.1 F8000 ; wipe mouth to avoid filament stick to heatbed\n  G90\n  G1 X128 Y128 F30000\n  G28 Z P0 T400\n  M400\n;===== first homign end =====\n\n;===== detection start =====\n  M1002 gcode_claim_action : 11\n  M104 S{nozzle_temperature_initial_layer[initial_no_support_filament_id]-80} A ; rise temp in advance\n  M972 S19 P0 T5000 ;plate type detection\n\n  {if max_print_z >= 145}\n    M1002 gcode_claim_action : 75 ;  Detect obstacles at the botton of the heated bed\n    G150.3\n    M104 S{nozzle_temperature_initial_layer[initial_no_support_filament_id]} ; rise temp in advance\n    G3811 Z{max_print_z}  ; Detect obstacles at the bottom of the heated bed\n  {endif}\n;===== detection end =====\n\n;===== prepare print temperature and material ==========\n  M400\n  M211 X0 Y0 Z0 ;turn off soft endstop\n  M975 S1 ; turn on input shaping\n\n  G29.2 S0 ; avoid invalid abl data\n  G150.3\n{if ((filament_type[initial_no_support_filament_id] == \"PLA\") || (filament_type[initial_no_support_filament_id] == \"PLA-CF\") || (filament_type[initial_no_support_filament_id] == \"PETG\")) && (nozzle_diameter_at_nozzle_id[initial_nozzle_id] == 0.2)}\nM620.10 A0 F74.8347 H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} T{flush_temperatures[initial_no_support_filament_id]} P{nozzle_temperature_initial_layer[initial_no_support_filament_id]} S1\nM620.10 A1 F74.8347 H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} T{flush_temperatures[initial_no_support_filament_id]} P{nozzle_temperature_initial_layer[initial_no_support_filament_id]} S1\n{else}\nM620.10 A0 F{flush_volumetric_speeds[initial_no_support_filament_id]/2.4053*60} H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} T{flush_temperatures[initial_no_support_filament_id]} P{nozzle_temperature_initial_layer[initial_no_support_filament_id]} S1\nM620.10 A1 F{flush_volumetric_speeds[initial_no_support_filament_id]/2.4053*60} H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} T{flush_temperatures[initial_no_support_filament_id]} P{nozzle_temperature_initial_layer[initial_no_support_filament_id]} S1\n{endif}\n\n M620.11 P0 L0 I[initial_no_support_filament_id] E0\n M620.11 K0 I[initial_no_support_filament_id] R0\n\n  M620 S[initial_no_support_filament_id]A   ; switch material if AMS exist\n  M1002 gcode_claim_action : 4\n  M1002 set_filament_type:UNKNOWN\n  M400\n  T[initial_no_support_filament_id]\n  M400\n  M628 S0\n  M629\n  M400\n  M1002 set_filament_type:{filament_type[initial_no_support_filament_id]}\n  M621 S[initial_no_support_filament_id]A\n  M104 S{nozzle_temperature_initial_layer[initial_no_support_filament_id]}\n  M400\n  M106 P1 S0\n  M400\n  G29.2 S1\n;===== prepare print temperature and material ==========\n\n\n;===== auto extrude cali start =========================\n  M975 S1\n  M1002 judge_flag extrude_cali_flag\n  M622 J0\n    M983.3 F{filament_max_volumetric_speed[initial_no_support_filament_id]/2.4} A0.4 ; cali dynamic extrusion compensation\n  M623\n\n  M622 J1\n    M1002 set_filament_type:{filament_type[initial_no_support_filament_id]}\n    M1002 gcode_claim_action : 8\n    M109 S{nozzle_temperature[initial_no_support_filament_id]}\n    G90\n    M83\n    M983.3 F{filament_max_volumetric_speed[initial_no_support_filament_id]/2.4} A0.4 ; cali dynamic extrusion compensation\n    M400\n    M106 P1 S255\n    M400 S5\n    M106 P1 S0\n    G150.3\n  M623\n\n  M622 J2\n    M1002 set_filament_type:{filament_type[initial_no_support_filament_id]}\n    M1002 gcode_claim_action : 8\n    M109 S{nozzle_temperature[initial_no_support_filament_id]}\n    G90\n    M83\n    M983.3 F{filament_max_volumetric_speed[initial_no_support_filament_id]/2.4} A0.4 ; cali dynamic extrusion compensation\n    M400\n    M106 P1 S255\n    M400 S5\n    M106 P1 S0\n    G150.3\n  M623\n;===== auto extrude cali end =========================\n\n  {if hold_chamber_temp_for_flat_print}\n    M1002 gcode_claim_action : 58\n    M104 S{first_layer_temperature[initial_no_support_filament_id]}\n    {if bed_temperature_initial_layer_single > 89}\n        M1030 S1800\n        SYNC R0 T1800\n    {else}\n        M1030 S300\n        SYNC R0 T300\n    {endif}\n    M1030 C\n  {endif}\n\n  {if filament_type[initial_filament_id] == \"TPU\" || filament_type[initial_filament_id] == \"PVA\"}\n  {else}\n    M83\n    G1 E-3 F1800\n    M400 P500\n  {endif}\n  G150.2\n  G150.1 F8000\n  G150.2\n  G150.1 F8000\n\n  G91\n  G1 Y-16 F12000 ; move away from the trash bin\n  G90\n  M400\n\n  M104 S{nozzle_temperature_initial_layer[initial_no_support_filament_id]-80} A\n\n;===== wipe right nozzle start =====\n  M1002 gcode_claim_action : 14\n  G150 T{nozzle_temperature_initial_layer[initial_no_support_filament_id]}\n  M400\n\n{if filament_type[initial_filament_id] == \"PC\"}\n  M109 S170 A\n{else}\n  M109 S140 A\n{endif}\n  G91\n  G1 Z5 F1200\n  G90\n  M400\n  G150.1\n;===== wipe left nozzle end =====\n\n\n;===== mech mode sweep start =====\n  M1002 gcode_claim_action : 3\n  G90\n  G1 X128 Y128 F20000\n  G1 Z5 F1200\n  M400 P200\n  M970.3 Q1 A5 K0 O1\n  M970.2 Q1 K1 W74 Z0.01\n  M974 Q1 S2 P0\n  M970.3 Q0 A7 K0 O1\n  M970.2 Q0 K1 W74 Z0.01\n  M974 Q0 S2 P0\n  M975 S1\n  M400\n;===== mech mode sweep end =====\n\n;===== bed leveling ==================================\n  M1002 gcode_claim_action : 54\n  M190 S[bed_temperature_initial_layer_single]; ensure bed temp\n  M109 S140 A\n  M106 S0 ; turn off fan , too noisy\n  M1002 judge_flag g29_before_print_flag\n  M622 J1\n    M1002 gcode_claim_action : 1\n    {if hold_chamber_temp_for_flat_print}\n      G29 H\n    {else}\n      G29 A1 X{first_layer_print_min[0]} Y{first_layer_print_min[1]} I{first_layer_print_size[0]} J{first_layer_print_size[1]}\n    {endif}\n    M400\n  M623\n\n  M622 J2\n    M1002 gcode_claim_action : 1\n    {if hold_chamber_temp_for_flat_print}\n      G29 H\n    {else}\n      G29 A2 X{first_layer_print_min[0]} Y{first_layer_print_min[1]} I{first_layer_print_size[0]} J{first_layer_print_size[1]}\n    {endif}\n    M400\n  M623\n\n  M622 J0\n    G28\n  M623\n  G29.2 S1\n  G28\n;===== bed leveling end ================================\n\n  M985.1 U0 E2\n  M985.1 U1 E2\n\n  M104 S{nozzle_temperature_initial_layer[initial_filament_id]} A\n  G150.3 ; move to garbage can to wait for temp\n\n;===== wait temperature reaching the reference value =======\n  M190 S[bed_temperature_initial_layer_single]\n\n  ;========turn off light and fans =============\n  M960 S1 P0 ; turn off laser\n  M960 S2 P0 ; turn off laser\n  M106 S0 ; turn off cooling fan\n\n;===== wait temperature reaching the reference value =======\n\n  M1002 gcode_claim_action : 255\n  M400\n  M975 S1 ; turn on mech mode supression\n\n;============switch again==================\n  M211 X0 Y0 Z0 ;turn off soft endstop\n  G91\n  G1 Z6 F1200\n  G90\n  M1002 set_filament_type:{filament_type[initial_no_support_filament_id]}\n  M620 S[initial_no_support_filament_id]A\n  M400\n  T[initial_no_support_filament_id]\n  M400\n  M628 S0\n  M629\n  M400\n  M621 S[initial_no_support_filament_id]A\n;============switch again==================\n\n;===== for Textured PEI Plate , lower the nozzle as the nozzle was touching topmost of the texture when homing ==\n  {if bed_temperature_initial_layer_single > 89}\n    {if curr_bed_type==\"Textured PEI Plate\"}\n      G29.1 Z{-0.02} ; for Textured PEI Plate\n    {else}\n      G29.1 Z{0.0}\n    {endif}\n  {else}\n    {if curr_bed_type==\"Textured PEI Plate\"}\n      G29.1 Z{0.01} ; for Textured PEI Plate\n    {else}\n      G29.1 Z{0.03}\n    {endif}\n  {endif}\n\n\n;===== nozzle load line ===============================\nM1002 gcode_claim_action : 51\n  G29.2 S1 ; ensure z comp turn on\n  G90\n  M83\n  M400 P50\n  M500 D1\n  M400 S3\n  M109 S{nozzle_temperature_initial_layer[initial_no_support_filament_id]}\n  G0 X100 Y0 F24000\n  M400\n  ;G130 O0 X100 Y-0.4 Z0.8 F{filament_max_volumetric_speed[initial_no_support_filament_id]/2/2.4053} L40 E20 D5\n  G130 O0 X100 Y-0.2 Z0.6 F{filament_max_volumetric_speed[initial_no_support_filament_id]/2/2.4053} L40 E12 D4\n  G90\n  M83\n  G1 Z1\n  M400\n;===== noozle load line end ===========================\nM1002 gcode_claim_action : 0\n  G29.99\n\n{if (filament_type[initial_no_support_filament_id] == \"TPU\") ||\n(filament_type[initial_no_support_filament_id] == \"PLA\") ||  (filament_type[initial_no_support_filament_id] == \"PETG\")}\nM1015.3 S1 H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]};enable tpu, pla and petg clog detect\n{else}\nM1015.3 S0;disable clog detect\n{endif}\n\n{if (filament_type[initial_no_support_filament_id] == \"PLA\") ||  (filament_type[initial_no_support_filament_id] == \"PETG\")\n ||  (filament_type[initial_no_support_filament_id] == \"PLA-CF\")  ||  (filament_type[initial_no_support_filament_id] == \"PETG-CF\")}\nM1015.4 S1 K1 H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} ;enable E air printing detect\n{else}\nM1015.4 S0 K0 H{nozzle_diameter_at_nozzle_id[initial_nozzle_id]} ;disable E air printing detect\n{endif}\n\nM620.6 I[initial_no_support_filament_id] W1 ;enable ams air printing detect\n\nM1010 Q0 B0.023 S0.01\nM1010 Q1 B0.005 S0.01\nM1010.1 S1\n
; machine_switch_extruder_time = 0
; machine_unload_filament_time = 31
; master_extruder_id = 1
; max_bridge_length = 0
; max_layer_height = 0.28
; max_travel_detour_distance = 0
; min_bead_width = 85%
; min_feature_size = 25%
; min_layer_height = 0.08
; minimum_sparse_infill_area = 15
; mmu_segmented_region_interlocking_depth = 0
; mmu_segmented_region_max_width = 0
; monotonic_travel_into_wall = 45%
; no_slow_down_for_cooling_on_outwalls = 0
; nozzle_diameter = 0.4
; nozzle_flush_dataset = 0
; nozzle_height = 4.2
; nozzle_temperature = 230
; nozzle_temperature_initial_layer = 230
; nozzle_temperature_range_high = 250
; nozzle_temperature_range_low = 210
; nozzle_type = hardened_steel
; nozzle_volume = 110
; nozzle_volume_type = Standard
; only_one_wall_first_layer = 0
; ooze_prevention = 0
; other_layers_print_sequence = 0
; other_layers_print_sequence_nums = 0
; outer_wall_acceleration = 6000
; outer_wall_jerk = 9
; outer_wall_line_width = 0.42
; outer_wall_speed = 200
; overhang_1_4_speed = 0
; overhang_2_4_speed = 50
; overhang_3_4_speed = 30
; overhang_4_4_speed = 10
; overhang_fan_speed = 100
; overhang_fan_threshold = 50%
; overhang_threshold_participating_cooling = 95%
; overhang_totally_speed = 10
; override_filament_scarf_seam_setting = 0
; override_process_overhang_speed = 0
; physical_extruder_map = 0
; post_process = 
; pre_start_fan_time = 0
; precise_outer_wall = 0
; precise_z_height = 0
; pressure_advance = 0.02
; prime_tower_brim_width = 3
; prime_tower_enable_framework = 0
; prime_tower_extra_rib_length = 0
; prime_tower_fillet_wall = 1
; prime_tower_flat_ironing = 1
; prime_tower_infill_gap = 150%
; prime_tower_lift_height = -1
; prime_tower_lift_speed = 90
; prime_tower_max_speed = 90
; prime_tower_rib_wall = 1
; prime_tower_rib_width = 8
; prime_tower_skip_points = 1
; prime_tower_width = 35
; prime_volume_mode = Default
; print_compatible_printers = "Bambu Lab P2S 0.4 nozzle"
; print_extruder_id = 1
; print_extruder_variant = "Direct Drive Standard"
; print_flow_ratio = 1
; print_in_clockwise = 1
; print_sequence = by layer
; print_settings_id = 0.20mm Black Zone Frame @BBL P2S
; printable_area = 0x0,256x0,256x256,0x256
; printable_height = 256
; printer_extruder_id = 1
; printer_extruder_variant = "Direct Drive Standard"
; printer_model = Bambu Lab P2S
; printer_notes = 
; printer_settings_id = Bambu Lab P2S 0.4 nozzle
; printer_structure = corexy
; printer_technology = FFF
; printer_variant = 0.4
; printing_by_object_gcode = 
; process_notes = 
; raft_contact_distance = 0.1
; raft_expansion = 1.5
; raft_first_layer_density = 90%
; raft_first_layer_expansion = -1
; raft_layers = 0
; reduce_crossing_wall = 0
; reduce_fan_stop_start_freq = 1
; reduce_infill_retraction_mode = Auto
; required_nozzle_HRC = 40
; resolution = 0.012
; retract_before_wipe = 0%
; retract_length_toolchange = 2
; retract_lift_above = 0
; retract_lift_below = 249
; retract_restart_extra = 0
; retract_restart_extra_toolchange = 0
; retract_when_changing_layer = 1
; retraction_distances_when_cut = 18
; retraction_distances_when_ec = 0
; retraction_length = 0.8
; retraction_minimum_travel = 1
; retraction_speed = 30
; role_base_wipe_speed = 1
; scan_first_layer = 0
; scarf_angle_threshold = 155
; seam_gap = 15%
; seam_placement_away_from_overhangs = 0
; seam_position = aligned
; seam_slope_conditional = 1
; seam_slope_entire_loop = 0
; seam_slope_gap = 0
; seam_slope_inner_walls = 1
; seam_slope_min_length = 10
; seam_slope_start_height = 10%
; seam_slope_steps = 10
; seam_slope_type = none
; silent_mode = 0
; single_extruder_multi_material = 1
; skeleton_infill_density = 15%
; skeleton_infill_line_width = 0.45
; skin_infill_density = 15%
; skin_infill_depth = 2
; skin_infill_line_width = 0.45
; skirt_distance = 2
; skirt_height = 1
; skirt_loops = 0
; skirt_per_object = 1
; slice_closing_radius = 0.049
; slicing_mode = regular
; slow_down_for_layer_cooling = 1
; slow_down_layer_time = 8
; slow_down_min_speed = 20
; slowdown_end_acc = 100000
; slowdown_end_height = 400
; slowdown_end_speed = 1000
; slowdown_start_acc = 100000
; slowdown_start_height = 0
; slowdown_start_speed = 1000
; small_perimeter_speed = 50%
; small_perimeter_threshold = 0
; smooth_coefficient = 4
; smooth_speed_discontinuity_area = 1
; solid_infill_filament = 0
; sparse_infill_acceleration = 100%
; sparse_infill_anchor = 400%
; sparse_infill_anchor_max = 20
; sparse_infill_density = 15%
; sparse_infill_filament = 0
; sparse_infill_lattice_angle_1 = -45
; sparse_infill_lattice_angle_2 = 45
; sparse_infill_line_width = 0.45
; sparse_infill_pattern = grid
; sparse_infill_speed = 270
; spiral_mode = 0
; spiral_mode_max_xy_smoothing = 200%
; spiral_mode_smooth = 0
; standby_temperature_delta = -5
; start_end_points = 30x-3,54x245
; supertack_plate_temp = 50
; supertack_plate_temp_initial_layer = 50
; support_air_filtration = 0
; support_angle = 0
; support_base_pattern = default
; support_base_pattern_spacing = 2.5
; support_bottom_interface_spacing = 0.5
; support_bottom_z_distance = 0.2
; support_chamber_temp_control = 0
; support_cooling_filter = 0
; support_critical_regions_only = 0
; support_expansion = 0
; support_fast_purge_mode = 0
; support_filament = 0
; support_interface_bottom_layers = 2
; support_interface_filament = 0
; support_interface_loop_pattern = 0
; support_interface_not_for_body = 1
; support_interface_pattern = auto
; support_interface_spacing = 0.5
; support_interface_speed = 80
; support_interface_top_layers = 2
; support_ironing_direction = 0
; support_ironing_flow = 10%
; support_ironing_inset = 0
; support_ironing_pattern = zig-zag
; support_ironing_spacing = 0.15
; support_ironing_speed = 30
; support_line_width = 0.42
; support_object_first_layer_gap = 0.2
; support_object_skip_flush = 1
; support_object_xy_distance = 0.35
; support_on_build_plate_only = 0
; support_remove_small_overhang = 1
; support_speed = 150
; support_style = default
; support_threshold_angle = 30
; support_top_z_distance = 0.2
; support_type = tree(auto)
; symmetric_infill_y_axis = 0
; temperature_vitrification = 45
; template_custom_gcode = 
; textured_plate_temp = 55
; textured_plate_temp_initial_layer = 55
; thick_bridges = 0
; thumbnail_size = 50x50
; time_lapse_gcode = ;======== P2S timelapes gcode ==========\n;===== 2025/06/16 ====\n; SKIPPABLE_START\n; SKIPTYPE: timelapse\nM622.1 S1 ; for prev firware, default turned on\n\nM1002 judge_flag timelapse_record_flag\nM622 J1\n{if timelapse_type == 0} ; timelapse without wipe tower\n  M971 S11 C10 O0\n  M1004 S5 P1  ; external shutter\n{elsif timelapse_type == 1} ; timelapse with wipe tower\n  G150.3 ; move to garbage can\n  M400\n  M1004 S5 P1  ; external shutter\n  M400 P300\n  M971 S11 C10 O0\n  M400 P350\n  \n  G90\n  G1 Z{max_layer_z + 3.0} F1200\n  G1 Y247 F30000\n  G1 Y217 F18000\n{endif}\nM623\n; SKIPPABLE_END\n
; timelapse_type = 0
; top_area_threshold = 200%
; top_color_penetration_layers = 5
; top_one_wall_type = all top
; top_shell_layers = 5
; top_shell_thickness = 1
; top_solid_infill_flow_ratio = 1
; top_surface_acceleration = 2000
; top_surface_density = 100%
; top_surface_jerk = 9
; top_surface_line_width = 0.42
; top_surface_pattern = monotonicline
; top_surface_speed = 200
; top_z_overrides_xy_distance = 0
; travel_acceleration = 10000
; travel_jerk = 9
; travel_short_distance_acceleration = 250
; travel_speed = 600
; travel_speed_z = 0
; tree_support_branch_angle = 45
; tree_support_branch_diameter = 2
; tree_support_branch_diameter_angle = 5
; tree_support_branch_distance = 5
; tree_support_wall_count = -1
; upward_compatible_machine = "Bambu Lab A1 0.4 nozzle";"Bambu Lab H2S 0.4 nozzle";"Bambu Lab H2D 0.4 nozzle";"Bambu Lab H2D Pro 0.4 nozzle";"Bambu Lab H2C 0.4 nozzle";"Bambu Lab X2D 0.4 nozzle";"Bambu Lab A2L 0.4 nozzle"
; use_firmware_retraction = 0
; use_relative_e_distances = 1
; vertical_shell_speed = 80%
; volumetric_speed_coefficients = "0 0 0 0 0 0"
; wall_distribution_count = 1
; wall_filament = 0
; wall_generator = classic
; wall_loops = 2
; wall_sequence = inner wall/outer wall
; wall_transition_angle = 10
; wall_transition_filter_deviation = 25%
; wall_transition_length = 100%
; wipe = 1
; wipe_distance = 2
; wipe_speed = 80%
; wipe_tower_no_sparse_layers = 0
; wipe_tower_rotation_angle = 0
; wipe_tower_x = 15
; wipe_tower_y = 220
; wrapping_detection_gcode = ;======== P2S 20250822 clumping ========\n{if !spiral_mode}\n    M622.1 S0 ; for previous firmware, default turn off\n    M1002 set_flag g39_forced_detection_flag=1\n    M1002 judge_flag g39_forced_detection_flag\n    M622 J1\n        {if layer_num == 3 || layer_num == 10 || layer_num == 19}\n            M993 A2 B2 C2 ; nozzle cam detection allow status save.\n            M993 A0 B0 C0 ; nozzle cam detection not allowed.\n\n            M400 P100\n\n            G39\n\n            G90\n            G1 Y247 F30000\n            G1 Y217 F18000\n            \n            M993 A3 B3 C3 ; nozzle cam detection allow status restore.\n        {endif}\n    M623\n{endif}
; wrapping_detection_layers = 20
; wrapping_exclude_area = 153x256,216x256,216x235,153x235
; xy_contour_compensation = 0
; xy_hole_compensation = 0
; z_direction_outwall_speed_continuous = 0
; z_hop = 0.4
; z_hop_types = Auto Lift
; CONFIG_BLOCK_END

; EXECUTABLE_BLOCK_START
M73 P0 R21
M201 X20000 Y20000 Z500 E5000
M203 X600 Y600 Z20 E30
M204 P20000 R5000 T20000
M205 X9.00 Y9.00 Z3.00 E2.50
M106 S0
M106 P2 S0
; FEATURE: Custom
;M1002 set_flag extrude_cali_flag=1
;M1002 set_flag g29_before_print_flag=1
;M1002 set_flag auto_cali_toolhead_offset_flag=1
;M1002 set_flag build_plate_detect_flag=1

;======== P2S start gcode==========
;===== 2026/05/18 =====

  M140 S55 ; heat heatbed first
  M993 A0 B0 C0 ; nozzle cam detection not allowed.
  M400

;=====printer start sound ===================
M17
M400 S1
M1006 S1
M1006 A53 B9 L50 C53 D9 M50 E53 F9 N50
M1006 A56 B9 L50 C56 D9 M50 E56 F9 N50
M1006 A61 B9 L50 C61 D9 M50 E61 F9 N50
M1006 A53 B9 L50 C53 D9 M50 E53 F9 N50
M1006 A56 B9 L50 C56 D9 M50 E56 F9 N50
M1006 A61 B18 L50 C61 D18 M50 E61 F18 N50
M1006 W
;=====printer start sound ===================

  M620 M ;enable remap
  G389

;===== avoid end stop =================
  G91
  G380 S2 Z22 F1200
  G380 S2 Z-12 F1200
  G90
;===== avoid end stop =================

;===== reset machine status =================
  M204 S10000
  M630 S0 P1
  G90
  M17 D ; reset motor current to default
  M960 S5 P1 ; turn on logo lamp
  G90
  M220 S100 ;Reset Feedrate
  M1002 set_gcode_claim_speed_level: 5
  M221 S100 ;Reset Flowrate
  M73.2   R1.0 ;Reset left time magnitude
  G29.1 Z0 ; clear z-trim value first
  M983.1 M1
  M982.2 S1 ; turn on cog noise reduction
  M983.4 S0
;===== reset machine status =================

;==== set airduct mode ====
;==== if Chamber Cooling is necessary ====


M145 P0 ; set airduct mode to cooling mode for cooling
M106 P2 S255 ; turn on auxiliary fan for cooling
M106 P3 S127 ; turn on chamber fan for cooling
M1002 gcode_claim_action : 29
M191 S0 ; wait for chamber temp
M106 P2 S102 ; turn on chamber cooling fan
M622.1 S0
M1002 judge_flag ventobox_replace_aux1_fan_flag
M622 J0
M106 P10 S0 ; turn off left aux fan
M623
M142 P6 R30 S40 U0.3 V0.8 ; set PETG exhaust chamber autocooling


;==== set airduct mode ====

;===== start to heat heatbed & hotend==========
  M1002 gcode_claim_action : 2
  M1002 set_filament_type:PLA-CF
  M104 S140 A

  G29.2 S0 ; avoid invalid abl data

;===== first homing start =====
  M1002 gcode_claim_action : 13
  G28 X T300
  G150.1 F8000 ; wipe mouth to avoid filament stick to heatbed
  G150.3
  M972 S24 P0
  M972 S26 P0 C0
  M972 S42 P0 T5000
  G150.1 F8000 ; wipe mouth to avoid filament stick to heatbed
  G90
  G1 X128 Y128 F30000
  G28 Z P0 T400
  M400
;===== first homign end =====

;===== detection start =====
  M1002 gcode_claim_action : 11
  M104 S150 A ; rise temp in advance
  M972 S19 P0 T5000 ;plate type detection

  
;===== detection end =====

;===== prepare print temperature and material ==========
  M400
  M211 X0 Y0 Z0 ;turn off soft endstop
  M975 S1 ; turn on input shaping

  G29.2 S0 ; avoid invalid abl data
  G150.3

M620.10 A0 F374.174 H0.4 T250 P230 S1
M620.10 A1 F374.174 H0.4 T250 P230 S1


 M620.11 P0 L0 I0 E0
 M620.11 K0 I0 R0

  M620 S0A   ; switch material if AMS exist
  M1002 gcode_claim_action : 4
  M1002 set_filament_type:UNKNOWN
  M400
  T0
  M400
  M628 S0
  M629
  M400
  M1002 set_filament_type:PLA-CF
  M621 S0A
  M104 S230
  M400
  M106 P1 S0
  M400
  G29.2 S1
;===== prepare print temperature and material ==========


;===== auto extrude cali start =========================
  M975 S1
  M1002 judge_flag extrude_cali_flag
  M622 J0
    M983.3 F6.25 A0.4 ; cali dynamic extrusion compensation
  M623

  M622 J1
    M1002 set_filament_type:PLA-CF
    M1002 gcode_claim_action : 8
    M109 S230
    G90
    M83
    M983.3 F6.25 A0.4 ; cali dynamic extrusion compensation
    M400
    M106 P1 S255
    M400 S5
    M106 P1 S0
    G150.3
  M623

  M622 J2
    M1002 set_filament_type:PLA-CF
    M1002 gcode_claim_action : 8
    M109 S230
    G90
    M83
    M983.3 F6.25 A0.4 ; cali dynamic extrusion compensation
    M400
    M106 P1 S255
    M400 S5
    M106 P1 S0
    G150.3
  M623
;===== auto extrude cali end =========================

  

  
    M83
    G1 E-3 F1800
    M400 P500
  
  G150.2
  G150.1 F8000
  G150.2
  G150.1 F8000

  G91
  G1 Y-16 F12000 ; move away from the trash bin
  G90
  M400

  M104 S150 A

;===== wipe right nozzle start =====
  M1002 gcode_claim_action : 14
  G150 T230
  M400


  M109 S140 A

  G91
M73 P2 R21
  G1 Z5 F1200
  G90
  M400
  G150.1
;===== wipe left nozzle end =====


;===== mech mode sweep start =====
  M1002 gcode_claim_action : 3
  G90
M73 P2 R20
  G1 X128 Y128 F20000
  G1 Z5 F1200
  M400 P200
  M970.3 Q1 A5 K0 O1
  M970.2 Q1 K1 W74 Z0.01
  M974 Q1 S2 P0
  M970.3 Q0 A7 K0 O1
  M970.2 Q0 K1 W74 Z0.01
  M974 Q0 S2 P0
  M975 S1
  M400
;===== mech mode sweep end =====

;===== bed leveling ==================================
  M1002 gcode_claim_action : 54
  M190 S55; ensure bed temp
  M109 S140 A
  M106 S0 ; turn off fan , too noisy
  M1002 judge_flag g29_before_print_flag
  M622 J1
    M1002 gcode_claim_action : 1
    
      G29 A1 X2.99999 Y28 I250 J200
    
    M400
  M623

  M622 J2
    M1002 gcode_claim_action : 1
    
      G29 A2 X2.99999 Y28 I250 J200
    
    M400
  M623

  M622 J0
    G28
  M623
  G29.2 S1
  G28
;===== bed leveling end ================================

  M985.1 U0 E2
  M985.1 U1 E2

  M104 S230 A
  G150.3 ; move to garbage can to wait for temp

;===== wait temperature reaching the reference value =======
  M190 S55

  ;========turn off light and fans =============
  M960 S1 P0 ; turn off laser
  M960 S2 P0 ; turn off laser
  M106 S0 ; turn off cooling fan

;===== wait temperature reaching the reference value =======

  M1002 gcode_claim_action : 255
  M400
  M975 S1 ; turn on mech mode supression

;============switch again==================
  M211 X0 Y0 Z0 ;turn off soft endstop
  G91
  G1 Z6 F1200
  G90
  M1002 set_filament_type:PLA-CF
  M620 S0A
  M400
  T0
  M400
  M628 S0
  M629
  M400
  M621 S0A
;============switch again==================

;===== for Textured PEI Plate , lower the nozzle as the nozzle was touching topmost of the texture when homing ==
  
    
      G29.1 Z0.01 ; for Textured PEI Plate
    
  


;===== nozzle load line ===============================
M1002 gcode_claim_action : 51
  G29.2 S1 ; ensure z comp turn on
  G90
  M83
  M400 P50
  M500 D1
  M400 S3
  M109 S230
  G0 X100 Y0 F24000
  M400
  ;G130 O0 X100 Y-0.4 Z0.8 F3.11811 L40 E20 D5
  G130 O0 X100 Y-0.2 Z0.6 F3.11811 L40 E12 D4
  G90
  M83
  G1 Z1
  M400
;===== noozle load line end ===========================
M1002 gcode_claim_action : 0
  G29.99


M1015.3 S0;disable clog detect



M1015.4 S1 K1 H0.4 ;enable E air printing detect


M620.6 I0 W1 ;enable ams air printing detect

M1010 Q0 B0.023 S0.01
M1010 Q1 B0.005 S0.01
M1010.1 S1
; MACHINE_START_GCODE_END
; filament start gcode
;VT0 H-1
G90
G21
M83 ; use relative distances for extrusion
M981 S1 P20000 ;open spaghetti detector
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; LAYER_HEIGHT: 0.2
G1 E-.8 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====









    
        M106 P2 S102
    

    M622.1 S0
    M1002 judge_flag ventobox_replace_aux1_fan_flag
    M622 J0
    M106 P10 S102; set first x_layer left aux fan
    M623
;not reset fan


; update layer progress
M73 L1
M991 S0 P0 ;notify layer change


M106 S0
; OBJECT_ID: 15
M73 P32 R14
G1 X247.857 Y33.6 F36000
M204 S6000
G1 Z.4
G1 Z.2
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.5
G1 F3000
M204 S500
G1 X247.857 Y33.143 E.01702
G1 X8.143 Y33.143 E8.92844
G1 X8.143 Y222.857 E7.06613
G1 X247.857 Y222.857 E8.92844
G1 X247.857 Y33.66 E7.04687
M204 S6000
G1 X247.4 Y33.6 F36000
; FEATURE: Outer wall
G1 F3000
M204 S500
M73 P33 R14
G1 X8.6 Y33.6 E8.89439
G1 X8.6 Y222.4 E7.03208
G1 X247.4 Y222.4 E8.89439
G1 X247.4 Y33.66 E7.02985
; WIPE_START
G1 X245.4 Y33.659 E-.76
; WIPE_END
G1 E-.04 F1800
M204 S6000
M73 P34 R14
G1 X245.666 Y41.287 Z.6 F36000
G1 X252.143 Y227.143 Z.6
M73 P35 R14
G1 Z.2
M73 P35 R13
G1 E.8 F1800
; FEATURE: Inner wall
G1 F3000
M204 S500
G1 X252.143 Y28.857 E7.3854
G1 X3.857 Y28.857 E9.24771
G1 X3.857 Y227.143 E7.3854
G1 X252.083 Y227.143 E9.24547
M204 S6000
G1 X252.6 Y227.6 F36000
; FEATURE: Outer wall
G1 F3000
M204 S500
G1 X252.6 Y28.4 E7.41944
M73 P36 R13
G1 X3.4 Y28.4 E9.28175
G1 X3.4 Y227.6 E7.41944
G1 X252.54 Y227.6 E9.27952
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

; WIPE_START
G1 X252.541 Y225.6 E-.76
; WIPE_END
G1 E-.04 F1800
M73 P37 R13
G1 X251.035 Y29.04 F36000
M204 S6000
G1 Z.6
G1 Z.2
M73 P38 R13
G1 E.8 F1800
; FEATURE: Bottom surface
; LINE_WIDTH: 0.50057
G1 F6300
M204 S500
G1 X251.754 Y29.759 E.03795
G1 X251.754 Y30.407 E.02414
G1 X250.593 Y29.246 E.06123
G1 X249.946 Y29.246 E.02414
G1 X251.754 Y31.054 E.09537
G1 X251.754 Y31.701 E.02414
G1 X249.299 Y29.246 E.1295
G1 X248.652 Y29.246 E.02414
G1 X251.754 Y32.348 E.16363
G1 X251.754 Y32.995 E.02414
G1 X248.005 Y29.246 E.19777
G1 X247.357 Y29.246 E.02414
G1 X251.754 Y33.643 E.2319
G1 X251.754 Y34.29 E.02414
G1 X246.71 Y29.246 E.26604
G1 X246.063 Y29.246 E.02414
G1 X251.754 Y34.937 E.30017
G1 X251.754 Y35.584 E.02414
G1 X245.416 Y29.246 E.3343
G1 X244.768 Y29.246 E.02414
G1 X251.754 Y36.232 E.36844
G1 X251.754 Y36.879 E.02414
G1 X248.246 Y33.37 E.18506
G1 X248.246 Y32.754 E.02295
G1 X247.63 Y32.754 E.02295
G1 X244.121 Y29.246 E.18506
G1 X243.474 Y29.246 E.02414
G1 X246.983 Y32.754 E.18506
G1 X246.336 Y32.754 E.02414
G1 X242.827 Y29.246 E.18506
G1 X242.18 Y29.246 E.02414
G1 X245.688 Y32.754 E.18506
G1 X245.041 Y32.754 E.02414
G1 X241.532 Y29.246 E.18506
G1 X240.885 Y29.246 E.02414
G1 X244.394 Y32.754 E.18506
G1 X243.747 Y32.754 E.02414
G1 X240.238 Y29.246 E.18506
G1 X239.591 Y29.246 E.02414
G1 X243.1 Y32.754 E.18506
G1 X242.452 Y32.754 E.02414
G1 X238.944 Y29.246 E.18506
G1 X238.296 Y29.246 E.02414
G1 X241.805 Y32.754 E.18506
G1 X241.158 Y32.754 E.02414
G1 X237.649 Y29.246 E.18506
G1 X237.002 Y29.246 E.02414
G1 X240.511 Y32.754 E.18506
G1 X239.864 Y32.754 E.02414
G1 X236.355 Y29.246 E.18506
G1 X235.707 Y29.246 E.02414
G1 X239.216 Y32.754 E.18506
G1 X238.569 Y32.754 E.02414
G1 X235.06 Y29.246 E.18506
G1 X234.413 Y29.246 E.02414
G1 X237.922 Y32.754 E.18506
G1 X237.275 Y32.754 E.02414
G1 X233.766 Y29.246 E.18506
G1 X233.119 Y29.246 E.02414
G1 X236.627 Y32.754 E.18506
G1 X235.98 Y32.754 E.02414
G1 X232.471 Y29.246 E.18506
G1 X231.824 Y29.246 E.02414
G1 X235.333 Y32.754 E.18506
G1 X234.686 Y32.754 E.02414
G1 X231.177 Y29.246 E.18506
G1 X230.53 Y29.246 E.02414
G1 X234.039 Y32.754 E.18506
G1 X233.391 Y32.754 E.02414
G1 X229.883 Y29.246 E.18506
G1 X229.235 Y29.246 E.02414
G1 X232.744 Y32.754 E.18506
G1 X232.097 Y32.754 E.02414
G1 X228.588 Y29.246 E.18506
G1 X227.941 Y29.246 E.02414
G1 X231.45 Y32.754 E.18506
G1 X230.802 Y32.754 E.02414
G1 X227.294 Y29.246 E.18506
G1 X226.646 Y29.246 E.02414
G1 X230.155 Y32.754 E.18506
G1 X229.508 Y32.754 E.02414
G1 X225.999 Y29.246 E.18506
G1 X225.352 Y29.246 E.02414
G1 X228.861 Y32.754 E.18506
G1 X228.214 Y32.754 E.02414
G1 X224.705 Y29.246 E.18506
G1 X224.058 Y29.246 E.02414
G1 X227.566 Y32.754 E.18506
G1 X226.919 Y32.754 E.02414
G1 X223.41 Y29.246 E.18506
G1 X222.763 Y29.246 E.02414
G1 X226.272 Y32.754 E.18506
G1 X225.625 Y32.754 E.02414
M73 P39 R13
G1 X222.116 Y29.246 E.18506
G1 X221.469 Y29.246 E.02414
G1 X224.978 Y32.754 E.18506
G1 X224.33 Y32.754 E.02414
G1 X220.822 Y29.246 E.18506
G1 X220.174 Y29.246 E.02414
G1 X223.683 Y32.754 E.18506
G1 X223.036 Y32.754 E.02414
G1 X219.527 Y29.246 E.18506
G1 X218.88 Y29.246 E.02414
G1 X222.389 Y32.754 E.18506
G1 X221.741 Y32.754 E.02414
G1 X218.233 Y29.246 E.18506
G1 X217.585 Y29.246 E.02414
G1 X221.094 Y32.754 E.18506
G1 X220.447 Y32.754 E.02414
G1 X216.938 Y29.246 E.18506
G1 X216.291 Y29.246 E.02414
G1 X219.8 Y32.754 E.18506
G1 X219.153 Y32.754 E.02414
G1 X215.644 Y29.246 E.18506
G1 X214.997 Y29.246 E.02414
G1 X218.505 Y32.754 E.18506
G1 X217.858 Y32.754 E.02414
G1 X214.349 Y29.246 E.18506
G1 X213.702 Y29.246 E.02414
G1 X217.211 Y32.754 E.18506
G1 X216.564 Y32.754 E.02414
G1 X213.055 Y29.246 E.18506
G1 X212.408 Y29.246 E.02414
G1 X215.917 Y32.754 E.18506
G1 X215.269 Y32.754 E.02414
G1 X211.76 Y29.246 E.18506
G1 X211.113 Y29.246 E.02414
G1 X214.622 Y32.754 E.18506
G1 X213.975 Y32.754 E.02414
G1 X210.466 Y29.246 E.18506
G1 X209.819 Y29.246 E.02414
G1 X213.328 Y32.754 E.18506
G1 X212.68 Y32.754 E.02414
G1 X209.172 Y29.246 E.18506
G1 X208.524 Y29.246 E.02414
G1 X212.033 Y32.754 E.18506
G1 X211.386 Y32.754 E.02414
G1 X207.877 Y29.246 E.18506
G1 X207.23 Y29.246 E.02414
G1 X210.739 Y32.754 E.18506
G1 X210.092 Y32.754 E.02414
G1 X206.583 Y29.246 E.18506
G1 X205.936 Y29.246 E.02414
G1 X209.444 Y32.754 E.18506
G1 X208.797 Y32.754 E.02414
G1 X205.288 Y29.246 E.18506
G1 X204.641 Y29.246 E.02414
G1 X208.15 Y32.754 E.18506
G1 X207.503 Y32.754 E.02414
G1 X203.994 Y29.246 E.18506
G1 X203.347 Y29.246 E.02414
G1 X206.856 Y32.754 E.18506
G1 X206.208 Y32.754 E.02414
G1 X202.699 Y29.246 E.18506
G1 X202.052 Y29.246 E.02414
G1 X205.561 Y32.754 E.18506
G1 X204.914 Y32.754 E.02414
G1 X201.405 Y29.246 E.18506
G1 X200.758 Y29.246 E.02414
G1 X204.267 Y32.754 E.18506
G1 X203.619 Y32.754 E.02414
G1 X200.111 Y29.246 E.18506
G1 X199.463 Y29.246 E.02414
G1 X202.972 Y32.754 E.18506
G1 X202.325 Y32.754 E.02414
G1 X198.816 Y29.246 E.18506
G1 X198.169 Y29.246 E.02414
G1 X201.678 Y32.754 E.18506
G1 X201.031 Y32.754 E.02414
G1 X197.522 Y29.246 E.18506
G1 X196.875 Y29.246 E.02414
G1 X200.383 Y32.754 E.18506
G1 X199.736 Y32.754 E.02414
G1 X196.227 Y29.246 E.18506
G1 X195.58 Y29.246 E.02414
G1 X199.089 Y32.754 E.18506
G1 X198.442 Y32.754 E.02414
G1 X194.933 Y29.246 E.18506
G1 X194.286 Y29.246 E.02414
G1 X197.795 Y32.754 E.18506
G1 X197.147 Y32.754 E.02414
G1 X193.638 Y29.246 E.18506
G1 X192.991 Y29.246 E.02414
M73 P39 R12
G1 X196.5 Y32.754 E.18506
G1 X195.853 Y32.754 E.02414
G1 X192.344 Y29.246 E.18506
G1 X191.697 Y29.246 E.02414
G1 X195.206 Y32.754 E.18506
G1 X194.558 Y32.754 E.02414
G1 X191.05 Y29.246 E.18506
G1 X190.402 Y29.246 E.02414
G1 X193.911 Y32.754 E.18506
G1 X193.264 Y32.754 E.02414
G1 X189.755 Y29.246 E.18506
G1 X189.108 Y29.246 E.02414
G1 X192.617 Y32.754 E.18506
G1 X191.97 Y32.754 E.02414
G1 X188.461 Y29.246 E.18506
G1 X187.814 Y29.246 E.02414
G1 X191.322 Y32.754 E.18506
G1 X190.675 Y32.754 E.02414
G1 X187.166 Y29.246 E.18506
G1 X186.519 Y29.246 E.02414
G1 X190.028 Y32.754 E.18506
G1 X189.381 Y32.754 E.02414
G1 X185.872 Y29.246 E.18506
G1 X185.225 Y29.246 E.02414
G1 X188.734 Y32.754 E.18506
G1 X188.086 Y32.754 E.02414
G1 X184.577 Y29.246 E.18506
G1 X183.93 Y29.246 E.02414
G1 X187.439 Y32.754 E.18506
G1 X186.792 Y32.754 E.02414
M73 P40 R12
G1 X183.283 Y29.246 E.18506
G1 X182.636 Y29.246 E.02414
G1 X186.145 Y32.754 E.18506
G1 X185.497 Y32.754 E.02414
G1 X181.989 Y29.246 E.18506
G1 X181.341 Y29.246 E.02414
G1 X184.85 Y32.754 E.18506
G1 X184.203 Y32.754 E.02414
G1 X180.694 Y29.246 E.18506
G1 X180.047 Y29.246 E.02414
G1 X183.556 Y32.754 E.18506
G1 X182.909 Y32.754 E.02414
G1 X179.4 Y29.246 E.18506
G1 X178.753 Y29.246 E.02414
G1 X182.261 Y32.754 E.18506
G1 X181.614 Y32.754 E.02414
G1 X178.105 Y29.246 E.18506
G1 X177.458 Y29.246 E.02414
G1 X180.967 Y32.754 E.18506
G1 X180.32 Y32.754 E.02414
G1 X176.811 Y29.246 E.18506
G1 X176.164 Y29.246 E.02414
G1 X179.673 Y32.754 E.18506
G1 X179.025 Y32.754 E.02414
G1 X175.516 Y29.246 E.18506
G1 X174.869 Y29.246 E.02414
G1 X178.378 Y32.754 E.18506
G1 X177.731 Y32.754 E.02414
G1 X174.222 Y29.246 E.18506
G1 X173.575 Y29.246 E.02414
G1 X177.084 Y32.754 E.18506
G1 X176.436 Y32.754 E.02414
G1 X172.928 Y29.246 E.18506
G1 X172.28 Y29.246 E.02414
G1 X175.789 Y32.754 E.18506
G1 X175.142 Y32.754 E.02414
G1 X171.633 Y29.246 E.18506
G1 X170.986 Y29.246 E.02414
G1 X174.495 Y32.754 E.18506
G1 X173.848 Y32.754 E.02414
G1 X170.339 Y29.246 E.18506
G1 X169.692 Y29.246 E.02414
G1 X173.2 Y32.754 E.18506
G1 X172.553 Y32.754 E.02414
G1 X169.044 Y29.246 E.18506
G1 X168.397 Y29.246 E.02414
G1 X171.906 Y32.754 E.18506
G1 X171.259 Y32.754 E.02414
G1 X167.75 Y29.246 E.18506
G1 X167.103 Y29.246 E.02414
G1 X170.612 Y32.754 E.18506
G1 X169.964 Y32.754 E.02414
G1 X166.455 Y29.246 E.18506
G1 X165.808 Y29.246 E.02414
G1 X169.317 Y32.754 E.18506
G1 X168.67 Y32.754 E.02414
G1 X165.161 Y29.246 E.18506
G1 X164.514 Y29.246 E.02414
G1 X168.023 Y32.754 E.18506
G1 X167.375 Y32.754 E.02414
G1 X163.867 Y29.246 E.18506
G1 X163.219 Y29.246 E.02414
G1 X166.728 Y32.754 E.18506
G1 X166.081 Y32.754 E.02414
G1 X162.572 Y29.246 E.18506
G1 X161.925 Y29.246 E.02414
G1 X165.434 Y32.754 E.18506
G1 X164.787 Y32.754 E.02414
G1 X161.278 Y29.246 E.18506
G1 X160.631 Y29.246 E.02414
G1 X164.139 Y32.754 E.18506
G1 X163.492 Y32.754 E.02414
G1 X159.983 Y29.246 E.18506
G1 X159.336 Y29.246 E.02414
G1 X162.845 Y32.754 E.18506
G1 X162.198 Y32.754 E.02414
G1 X158.689 Y29.246 E.18506
G1 X158.042 Y29.246 E.02414
G1 X161.551 Y32.754 E.18506
G1 X160.903 Y32.754 E.02414
G1 X157.394 Y29.246 E.18506
G1 X156.747 Y29.246 E.02414
G1 X160.256 Y32.754 E.18506
G1 X159.609 Y32.754 E.02414
G1 X156.1 Y29.246 E.18506
G1 X155.453 Y29.246 E.02414
G1 X158.962 Y32.754 E.18506
G1 X158.314 Y32.754 E.02414
G1 X154.806 Y29.246 E.18506
G1 X154.158 Y29.246 E.02414
G1 X157.667 Y32.754 E.18506
G1 X157.02 Y32.754 E.02414
G1 X153.511 Y29.246 E.18506
G1 X152.864 Y29.246 E.02414
G1 X156.373 Y32.754 E.18506
G1 X155.726 Y32.754 E.02414
G1 X152.217 Y29.246 E.18506
G1 X151.57 Y29.246 E.02414
G1 X155.078 Y32.754 E.18506
G1 X154.431 Y32.754 E.02414
G1 X150.922 Y29.246 E.18506
G1 X150.275 Y29.246 E.02414
G1 X153.784 Y32.754 E.18506
G1 X153.137 Y32.754 E.02414
G1 X149.628 Y29.246 E.18506
G1 X148.981 Y29.246 E.02414
G1 X152.49 Y32.754 E.18506
G1 X151.842 Y32.754 E.02414
G1 X148.333 Y29.246 E.18506
G1 X147.686 Y29.246 E.02414
G1 X151.195 Y32.754 E.18506
G1 X150.548 Y32.754 E.02414
G1 X147.039 Y29.246 E.18506
G1 X146.392 Y29.246 E.02414
G1 X149.901 Y32.754 E.18506
G1 X149.253 Y32.754 E.02414
G1 X145.745 Y29.246 E.18506
G1 X145.097 Y29.246 E.02414
G1 X148.606 Y32.754 E.18506
G1 X147.959 Y32.754 E.02414
G1 X144.45 Y29.246 E.18506
G1 X143.803 Y29.246 E.02414
M73 P41 R12
G1 X147.312 Y32.754 E.18506
G1 X146.665 Y32.754 E.02414
G1 X143.156 Y29.246 E.18506
G1 X142.509 Y29.246 E.02414
G1 X146.017 Y32.754 E.18506
G1 X145.37 Y32.754 E.02414
G1 X141.861 Y29.246 E.18506
G1 X141.214 Y29.246 E.02414
G1 X144.723 Y32.754 E.18506
G1 X144.076 Y32.754 E.02414
G1 X140.567 Y29.246 E.18506
G1 X139.92 Y29.246 E.02414
G1 X143.428 Y32.754 E.18506
G1 X142.781 Y32.754 E.02414
G1 X139.272 Y29.246 E.18506
G1 X138.625 Y29.246 E.02414
G1 X142.134 Y32.754 E.18506
G1 X141.487 Y32.754 E.02414
G1 X137.978 Y29.246 E.18506
G1 X137.331 Y29.246 E.02414
G1 X140.84 Y32.754 E.18506
G1 X140.192 Y32.754 E.02414
G1 X136.684 Y29.246 E.18506
G1 X136.036 Y29.246 E.02414
G1 X139.545 Y32.754 E.18506
G1 X138.898 Y32.754 E.02414
G1 X135.389 Y29.246 E.18506
G1 X134.742 Y29.246 E.02414
G1 X138.251 Y32.754 E.18506
G1 X137.604 Y32.754 E.02414
G1 X134.095 Y29.246 E.18506
G1 X133.448 Y29.246 E.02414
G1 X136.956 Y32.754 E.18506
G1 X136.309 Y32.754 E.02414
G1 X132.8 Y29.246 E.18506
G1 X132.153 Y29.246 E.02414
G1 X135.662 Y32.754 E.18506
G1 X135.015 Y32.754 E.02414
G1 X131.506 Y29.246 E.18506
G1 X130.859 Y29.246 E.02414
G1 X134.367 Y32.754 E.18506
G1 X133.72 Y32.754 E.02414
G1 X130.211 Y29.246 E.18506
G1 X129.564 Y29.246 E.02414
G1 X133.073 Y32.754 E.18506
G1 X132.426 Y32.754 E.02414
G1 X128.917 Y29.246 E.18506
G1 X128.27 Y29.246 E.02414
G1 X131.779 Y32.754 E.18506
G1 X131.131 Y32.754 E.02414
G1 X127.623 Y29.246 E.18506
G1 X126.975 Y29.246 E.02414
G1 X130.484 Y32.754 E.18506
G1 X129.837 Y32.754 E.02414
G1 X126.328 Y29.246 E.18506
G1 X125.681 Y29.246 E.02414
G1 X129.19 Y32.754 E.18506
G1 X128.543 Y32.754 E.02414
G1 X125.034 Y29.246 E.18506
G1 X124.386 Y29.246 E.02414
G1 X127.895 Y32.754 E.18506
G1 X127.248 Y32.754 E.02414
G1 X123.739 Y29.246 E.18506
G1 X123.092 Y29.246 E.02414
G1 X126.601 Y32.754 E.18506
G1 X125.954 Y32.754 E.02414
G1 X122.445 Y29.246 E.18506
G1 X121.798 Y29.246 E.02414
G1 X125.306 Y32.754 E.18506
G1 X124.659 Y32.754 E.02414
G1 X121.15 Y29.246 E.18506
G1 X120.503 Y29.246 E.02414
G1 X124.012 Y32.754 E.18506
G1 X123.365 Y32.754 E.02414
G1 X119.856 Y29.246 E.18506
G1 X119.209 Y29.246 E.02414
G1 X122.718 Y32.754 E.18506
G1 X122.07 Y32.754 E.02414
G1 X118.562 Y29.246 E.18506
G1 X117.914 Y29.246 E.02414
G1 X121.423 Y32.754 E.18506
G1 X120.776 Y32.754 E.02414
G1 X117.267 Y29.246 E.18506
G1 X116.62 Y29.246 E.02414
G1 X120.129 Y32.754 E.18506
G1 X119.482 Y32.754 E.02414
G1 X115.973 Y29.246 E.18506
G1 X115.325 Y29.246 E.02414
G1 X118.834 Y32.754 E.18506
G1 X118.187 Y32.754 E.02414
G1 X114.678 Y29.246 E.18506
G1 X114.031 Y29.246 E.02414
G1 X117.54 Y32.754 E.18506
G1 X116.893 Y32.754 E.02414
G1 X113.384 Y29.246 E.18506
G1 X112.737 Y29.246 E.02414
G1 X116.245 Y32.754 E.18506
G1 X115.598 Y32.754 E.02414
G1 X112.089 Y29.246 E.18506
G1 X111.442 Y29.246 E.02414
G1 X114.951 Y32.754 E.18506
G1 X114.304 Y32.754 E.02414
G1 X110.795 Y29.246 E.18506
G1 X110.148 Y29.246 E.02414
G1 X113.657 Y32.754 E.18506
G1 X113.009 Y32.754 E.02414
G1 X109.501 Y29.246 E.18506
G1 X108.853 Y29.246 E.02414
G1 X112.362 Y32.754 E.18506
G1 X111.715 Y32.754 E.02414
G1 X108.206 Y29.246 E.18506
G1 X107.559 Y29.246 E.02414
G1 X111.068 Y32.754 E.18506
G1 X110.421 Y32.754 E.02414
G1 X106.912 Y29.246 E.18506
G1 X106.264 Y29.246 E.02414
G1 X109.773 Y32.754 E.18506
G1 X109.126 Y32.754 E.02414
G1 X105.617 Y29.246 E.18506
G1 X104.97 Y29.246 E.02414
G1 X108.479 Y32.754 E.18506
G1 X107.832 Y32.754 E.02414
M73 P42 R12
G1 X104.323 Y29.246 E.18506
G1 X103.676 Y29.246 E.02414
G1 X107.184 Y32.754 E.18506
G1 X106.537 Y32.754 E.02414
G1 X103.028 Y29.246 E.18506
G1 X102.381 Y29.246 E.02414
G1 X105.89 Y32.754 E.18506
G1 X105.243 Y32.754 E.02414
G1 X101.734 Y29.246 E.18506
G1 X101.087 Y29.246 E.02414
G1 X104.596 Y32.754 E.18506
G1 X103.948 Y32.754 E.02414
G1 X100.44 Y29.246 E.18506
G1 X99.792 Y29.246 E.02414
G1 X103.301 Y32.754 E.18506
G1 X102.654 Y32.754 E.02414
G1 X99.145 Y29.246 E.18506
G1 X98.498 Y29.246 E.02414
G1 X102.007 Y32.754 E.18506
G1 X101.36 Y32.754 E.02414
G1 X97.851 Y29.246 E.18506
G1 X97.203 Y29.246 E.02414
G1 X100.712 Y32.754 E.18506
G1 X100.065 Y32.754 E.02414
G1 X96.556 Y29.246 E.18506
G1 X95.909 Y29.246 E.02414
G1 X99.418 Y32.754 E.18506
G1 X98.771 Y32.754 E.02414
G1 X95.262 Y29.246 E.18506
G1 X94.615 Y29.246 E.02414
G1 X98.123 Y32.754 E.18506
G1 X97.476 Y32.754 E.02414
G1 X93.967 Y29.246 E.18506
G1 X93.32 Y29.246 E.02414
G1 X96.829 Y32.754 E.18506
G1 X96.182 Y32.754 E.02414
G1 X92.673 Y29.246 E.18506
G1 X92.026 Y29.246 E.02414
G1 X95.535 Y32.754 E.18506
G1 X94.887 Y32.754 E.02414
G1 X91.379 Y29.246 E.18506
G1 X90.731 Y29.246 E.02414
G1 X94.24 Y32.754 E.18506
G1 X93.593 Y32.754 E.02414
G1 X90.084 Y29.246 E.18506
G1 X89.437 Y29.246 E.02414
G1 X92.946 Y32.754 E.18506
G1 X92.299 Y32.754 E.02414
G1 X88.79 Y29.246 E.18506
G1 X88.142 Y29.246 E.02414
G1 X91.651 Y32.754 E.18506
G1 X91.004 Y32.754 E.02414
G1 X87.495 Y29.246 E.18506
G1 X86.848 Y29.246 E.02414
G1 X90.357 Y32.754 E.18506
G1 X89.71 Y32.754 E.02414
G1 X86.201 Y29.246 E.18506
G1 X85.554 Y29.246 E.02414
G1 X89.062 Y32.754 E.18506
G1 X88.415 Y32.754 E.02414
G1 X84.906 Y29.246 E.18506
G1 X84.259 Y29.246 E.02414
G1 X87.768 Y32.754 E.18506
G1 X87.121 Y32.754 E.02414
G1 X83.612 Y29.246 E.18506
G1 X82.965 Y29.246 E.02414
G1 X86.474 Y32.754 E.18506
G1 X85.826 Y32.754 E.02414
G1 X82.318 Y29.246 E.18506
G1 X81.67 Y29.246 E.02414
G1 X85.179 Y32.754 E.18506
G1 X84.532 Y32.754 E.02414
G1 X81.023 Y29.246 E.18506
G1 X80.376 Y29.246 E.02414
G1 X83.885 Y32.754 E.18506
G1 X83.238 Y32.754 E.02414
G1 X79.729 Y29.246 E.18506
G1 X79.081 Y29.246 E.02414
G1 X82.59 Y32.754 E.18506
G1 X81.943 Y32.754 E.02414
G1 X78.434 Y29.246 E.18506
G1 X77.787 Y29.246 E.02414
G1 X81.296 Y32.754 E.18506
G1 X80.649 Y32.754 E.02414
G1 X77.14 Y29.246 E.18506
G1 X76.493 Y29.246 E.02414
G1 X80.001 Y32.754 E.18506
G1 X79.354 Y32.754 E.02414
G1 X75.845 Y29.246 E.18506
G1 X75.198 Y29.246 E.02414
G1 X78.707 Y32.754 E.18506
G1 X78.06 Y32.754 E.02414
G1 X74.551 Y29.246 E.18506
G1 X73.904 Y29.246 E.02414
G1 X77.413 Y32.754 E.18506
G1 X76.765 Y32.754 E.02414
G1 X73.257 Y29.246 E.18506
G1 X72.609 Y29.246 E.02414
G1 X76.118 Y32.754 E.18506
G1 X75.471 Y32.754 E.02414
G1 X71.962 Y29.246 E.18506
G1 X71.315 Y29.246 E.02414
G1 X74.824 Y32.754 E.18506
G1 X74.177 Y32.754 E.02414
G1 X70.668 Y29.246 E.18506
G1 X70.02 Y29.246 E.02414
G1 X73.529 Y32.754 E.18506
G1 X72.882 Y32.754 E.02414
G1 X69.373 Y29.246 E.18506
G1 X68.726 Y29.246 E.02414
G1 X72.235 Y32.754 E.18506
G1 X71.588 Y32.754 E.02414
G1 X68.079 Y29.246 E.18506
G1 X67.432 Y29.246 E.02414
G1 X70.94 Y32.754 E.18506
G1 X70.293 Y32.754 E.02414
G1 X66.784 Y29.246 E.18506
G1 X66.137 Y29.246 E.02414
G1 X69.646 Y32.754 E.18506
G1 X68.999 Y32.754 E.02414
G1 X65.49 Y29.246 E.18506
G1 X64.843 Y29.246 E.02414
M73 P43 R12
G1 X68.352 Y32.754 E.18506
G1 X67.704 Y32.754 E.02414
G1 X64.196 Y29.246 E.18506
G1 X63.548 Y29.246 E.02414
G1 X67.057 Y32.754 E.18506
G1 X66.41 Y32.754 E.02414
G1 X62.901 Y29.246 E.18506
G1 X62.254 Y29.246 E.02414
G1 X65.763 Y32.754 E.18506
G1 X65.115 Y32.754 E.02414
G1 X61.607 Y29.246 E.18506
G1 X60.959 Y29.246 E.02414
G1 X64.468 Y32.754 E.18506
G1 X63.821 Y32.754 E.02414
G1 X60.312 Y29.246 E.18506
G1 X59.665 Y29.246 E.02414
G1 X63.174 Y32.754 E.18506
G1 X62.527 Y32.754 E.02414
G1 X59.018 Y29.246 E.18506
G1 X58.371 Y29.246 E.02414
G1 X61.879 Y32.754 E.18506
G1 X61.232 Y32.754 E.02414
G1 X57.723 Y29.246 E.18506
G1 X57.076 Y29.246 E.02414
G1 X60.585 Y32.754 E.18506
G1 X59.938 Y32.754 E.02414
G1 X56.429 Y29.246 E.18506
G1 X55.782 Y29.246 E.02414
G1 X59.291 Y32.754 E.18506
G1 X58.643 Y32.754 E.02414
G1 X55.135 Y29.246 E.18506
G1 X54.487 Y29.246 E.02414
G1 X57.996 Y32.754 E.18506
G1 X57.349 Y32.754 E.02414
G1 X53.84 Y29.246 E.18506
G1 X53.193 Y29.246 E.02414
G1 X56.702 Y32.754 E.18506
G1 X56.054 Y32.754 E.02414
G1 X52.546 Y29.246 E.18506
G1 X51.898 Y29.246 E.02414
G1 X55.407 Y32.754 E.18506
G1 X54.76 Y32.754 E.02414
G1 X51.251 Y29.246 E.18506
G1 X50.604 Y29.246 E.02414
G1 X54.113 Y32.754 E.18506
G1 X53.466 Y32.754 E.02414
G1 X49.957 Y29.246 E.18506
G1 X49.31 Y29.246 E.02414
G1 X52.818 Y32.754 E.18506
G1 X52.171 Y32.754 E.02414
G1 X48.662 Y29.246 E.18506
G1 X48.015 Y29.246 E.02414
G1 X51.524 Y32.754 E.18506
G1 X50.877 Y32.754 E.02414
G1 X47.368 Y29.246 E.18506
G1 X46.721 Y29.246 E.02414
G1 X50.23 Y32.754 E.18506
G1 X49.582 Y32.754 E.02414
G1 X46.074 Y29.246 E.18506
G1 X45.426 Y29.246 E.02414
G1 X48.935 Y32.754 E.18506
G1 X48.288 Y32.754 E.02414
G1 X44.779 Y29.246 E.18506
G1 X44.132 Y29.246 E.02414
G1 X47.641 Y32.754 E.18506
G1 X46.993 Y32.754 E.02414
G1 X43.485 Y29.246 E.18506
G1 X42.837 Y29.246 E.02414
G1 X46.346 Y32.754 E.18506
G1 X45.699 Y32.754 E.02414
G1 X42.19 Y29.246 E.18506
G1 X41.543 Y29.246 E.02414
G1 X45.052 Y32.754 E.18506
G1 X44.405 Y32.754 E.02414
G1 X40.896 Y29.246 E.18506
G1 X40.249 Y29.246 E.02414
G1 X43.757 Y32.754 E.18506
G1 X43.11 Y32.754 E.02414
G1 X39.601 Y29.246 E.18506
G1 X38.954 Y29.246 E.02414
G1 X42.463 Y32.754 E.18506
G1 X41.816 Y32.754 E.02414
G1 X38.307 Y29.246 E.18506
G1 X37.66 Y29.246 E.02414
G1 X41.169 Y32.754 E.18506
G1 X40.521 Y32.754 E.02414
G1 X37.012 Y29.246 E.18506
G1 X36.365 Y29.246 E.02414
G1 X39.874 Y32.754 E.18506
G1 X39.227 Y32.754 E.02414
G1 X35.718 Y29.246 E.18506
G1 X35.071 Y29.246 E.02414
G1 X38.58 Y32.754 E.18506
G1 X37.932 Y32.754 E.02414
G1 X34.424 Y29.246 E.18506
G1 X33.776 Y29.246 E.02414
G1 X37.285 Y32.754 E.18506
G1 X36.638 Y32.754 E.02414
G1 X33.129 Y29.246 E.18506
G1 X32.482 Y29.246 E.02414
G1 X35.991 Y32.754 E.18506
G1 X35.344 Y32.754 E.02414
G1 X31.835 Y29.246 E.18506
G1 X31.188 Y29.246 E.02414
G1 X34.696 Y32.754 E.18506
G1 X34.049 Y32.754 E.02414
G1 X30.54 Y29.246 E.18506
G1 X29.893 Y29.246 E.02414
G1 X33.402 Y32.754 E.18506
G1 X32.755 Y32.754 E.02414
G1 X29.246 Y29.246 E.18506
G1 X28.599 Y29.246 E.02414
G1 X32.108 Y32.754 E.18506
G1 X31.46 Y32.754 E.02414
G1 X27.951 Y29.246 E.18506
G1 X27.304 Y29.246 E.02414
G1 X30.813 Y32.754 E.18506
G1 X30.166 Y32.754 E.02414
G1 X26.657 Y29.246 E.18506
G1 X26.01 Y29.246 E.02414
G1 X29.519 Y32.754 E.18506
M73 P44 R12
G1 X28.871 Y32.754 E.02414
G1 X25.363 Y29.246 E.18506
G1 X24.715 Y29.246 E.02414
G1 X28.224 Y32.754 E.18506
G1 X27.577 Y32.754 E.02414
G1 X24.068 Y29.246 E.18506
G1 X23.421 Y29.246 E.02414
G1 X26.93 Y32.754 E.18506
G1 X26.283 Y32.754 E.02414
G1 X22.774 Y29.246 E.18506
G1 X22.127 Y29.246 E.02414
G1 X25.635 Y32.754 E.18506
G1 X24.988 Y32.754 E.02414
G1 X21.479 Y29.246 E.18506
G1 X20.832 Y29.246 E.02414
G1 X24.341 Y32.754 E.18506
G1 X23.694 Y32.754 E.02414
G1 X20.185 Y29.246 E.18506
G1 X19.538 Y29.246 E.02414
G1 X23.047 Y32.754 E.18506
G1 X22.399 Y32.754 E.02414
G1 X18.89 Y29.246 E.18506
G1 X18.243 Y29.246 E.02414
G1 X21.752 Y32.754 E.18506
G1 X21.105 Y32.754 E.02414
G1 X17.596 Y29.246 E.18506
G1 X16.949 Y29.246 E.02414
G1 X20.458 Y32.754 E.18506
G1 X19.81 Y32.754 E.02414
G1 X16.302 Y29.246 E.18506
G1 X15.654 Y29.246 E.02414
G1 X19.163 Y32.754 E.18506
G1 X18.516 Y32.754 E.02414
G1 X15.007 Y29.246 E.18506
G1 X14.36 Y29.246 E.02414
G1 X17.869 Y32.754 E.18506
G1 X17.222 Y32.754 E.02414
G1 X13.713 Y29.246 E.18506
G1 X13.066 Y29.246 E.02414
G1 X16.574 Y32.754 E.18506
G1 X15.927 Y32.754 E.02414
G1 X12.418 Y29.246 E.18506
G1 X11.771 Y29.246 E.02414
G1 X15.28 Y32.754 E.18506
G1 X14.633 Y32.754 E.02414
G1 X11.124 Y29.246 E.18506
G1 X10.477 Y29.246 E.02414
M73 P44 R11
G1 X13.986 Y32.754 E.18506
G1 X13.338 Y32.754 E.02414
G1 X9.829 Y29.246 E.18506
G1 X9.182 Y29.246 E.02414
G1 X12.691 Y32.754 E.18506
G1 X12.044 Y32.754 E.02414
G1 X8.535 Y29.246 E.18506
G1 X7.888 Y29.246 E.02414
G1 X11.397 Y32.754 E.18506
G1 X10.749 Y32.754 E.02414
G1 X7.241 Y29.246 E.18506
G1 X6.593 Y29.246 E.02414
G1 X10.102 Y32.754 E.18506
G1 X9.455 Y32.754 E.02414
G1 X5.946 Y29.246 E.18506
G1 X5.299 Y29.246 E.02414
G1 X8.808 Y32.754 E.18506
G1 X8.161 Y32.754 E.02414
G1 X4.652 Y29.246 E.18506
G1 X4.246 Y29.246 E.01515
G1 X4.246 Y29.487 E.00899
G1 X7.754 Y32.995 E.18506
G1 X7.754 Y33.643 E.02414
G1 X4.246 Y30.134 E.18506
G1 X4.246 Y30.781 E.02414
G1 X7.754 Y34.29 E.18506
G1 X7.754 Y34.937 E.02414
G1 X4.246 Y31.428 E.18506
G1 X4.246 Y32.075 E.02414
G1 X7.754 Y35.584 E.18506
G1 X7.754 Y36.232 E.02414
G1 X4.246 Y32.723 E.18506
G1 X4.246 Y33.37 E.02414
G1 X7.754 Y36.879 E.18506
G1 X7.754 Y37.526 E.02414
G1 X4.246 Y34.017 E.18506
G1 X4.246 Y34.664 E.02414
G1 X7.754 Y38.173 E.18506
G1 X7.754 Y38.82 E.02414
G1 X4.246 Y35.312 E.18506
G1 X4.246 Y35.959 E.02414
G1 X7.754 Y39.468 E.18506
G1 X7.754 Y40.115 E.02414
G1 X4.246 Y36.606 E.18506
G1 X4.246 Y37.253 E.02414
G1 X7.754 Y40.762 E.18506
G1 X7.754 Y41.409 E.02414
G1 X4.246 Y37.9 E.18506
G1 X4.246 Y38.548 E.02414
G1 X7.754 Y42.056 E.18506
G1 X7.754 Y42.704 E.02414
G1 X4.246 Y39.195 E.18506
G1 X4.246 Y39.842 E.02414
G1 X7.754 Y43.351 E.18506
G1 X7.754 Y43.998 E.02414
G1 X4.246 Y40.489 E.18506
G1 X4.246 Y41.136 E.02414
G1 X7.754 Y44.645 E.18506
G1 X7.754 Y45.293 E.02414
G1 X4.246 Y41.784 E.18506
G1 X4.246 Y42.431 E.02414
G1 X7.754 Y45.94 E.18506
G1 X7.754 Y46.587 E.02414
G1 X4.246 Y43.078 E.18506
G1 X4.246 Y43.725 E.02414
G1 X7.754 Y47.234 E.18506
G1 X7.754 Y47.881 E.02414
G1 X4.246 Y44.373 E.18506
G1 X4.246 Y45.02 E.02414
G1 X7.754 Y48.529 E.18506
G1 X7.754 Y49.176 E.02414
G1 X4.246 Y45.667 E.18506
G1 X4.246 Y46.314 E.02414
G1 X7.754 Y49.823 E.18506
G1 X7.754 Y50.47 E.02414
M73 P45 R11
G1 X4.246 Y46.961 E.18506
G1 X4.246 Y47.609 E.02414
G1 X7.754 Y51.117 E.18506
G1 X7.754 Y51.765 E.02414
G1 X4.246 Y48.256 E.18506
G1 X4.246 Y48.903 E.02414
G1 X7.754 Y52.412 E.18506
G1 X7.754 Y53.059 E.02414
G1 X4.246 Y49.55 E.18506
G1 X4.246 Y50.197 E.02414
G1 X7.754 Y53.706 E.18506
G1 X7.754 Y54.354 E.02414
G1 X4.246 Y50.845 E.18506
G1 X4.246 Y51.492 E.02414
G1 X7.754 Y55.001 E.18506
G1 X7.754 Y55.648 E.02414
G1 X4.246 Y52.139 E.18506
G1 X4.246 Y52.786 E.02414
G1 X7.754 Y56.295 E.18506
G1 X7.754 Y56.942 E.02414
G1 X4.246 Y53.434 E.18506
G1 X4.246 Y54.081 E.02414
G1 X7.754 Y57.59 E.18506
G1 X7.754 Y58.237 E.02414
G1 X4.246 Y54.728 E.18506
G1 X4.246 Y55.375 E.02414
G1 X7.754 Y58.884 E.18506
G1 X7.754 Y59.531 E.02414
G1 X4.246 Y56.022 E.18506
G1 X4.246 Y56.67 E.02414
G1 X7.754 Y60.178 E.18506
G1 X7.754 Y60.826 E.02414
G1 X4.246 Y57.317 E.18506
G1 X4.246 Y57.964 E.02414
G1 X7.754 Y61.473 E.18506
G1 X7.754 Y62.12 E.02414
G1 X4.246 Y58.611 E.18506
G1 X4.246 Y59.258 E.02414
G1 X7.754 Y62.767 E.18506
G1 X7.754 Y63.415 E.02414
G1 X4.246 Y59.906 E.18506
G1 X4.246 Y60.553 E.02414
G1 X7.754 Y64.062 E.18506
G1 X7.754 Y64.709 E.02414
G1 X4.246 Y61.2 E.18506
G1 X4.246 Y61.847 E.02414
G1 X7.754 Y65.356 E.18506
G1 X7.754 Y66.003 E.02414
G1 X4.246 Y62.495 E.18506
G1 X4.246 Y63.142 E.02414
G1 X7.754 Y66.651 E.18506
G1 X7.754 Y67.298 E.02414
G1 X4.246 Y63.789 E.18506
G1 X4.246 Y64.436 E.02414
G1 X7.754 Y67.945 E.18506
G1 X7.754 Y68.592 E.02414
G1 X4.246 Y65.083 E.18506
G1 X4.246 Y65.731 E.02414
G1 X7.754 Y69.239 E.18506
G1 X7.754 Y69.887 E.02414
G1 X4.246 Y66.378 E.18506
G1 X4.246 Y67.025 E.02414
G1 X7.754 Y70.534 E.18506
G1 X7.754 Y71.181 E.02414
G1 X4.246 Y67.672 E.18506
G1 X4.246 Y68.32 E.02414
G1 X7.754 Y71.828 E.18506
G1 X7.754 Y72.476 E.02414
G1 X4.246 Y68.967 E.18506
G1 X4.246 Y69.614 E.02414
G1 X7.754 Y73.123 E.18506
G1 X7.754 Y73.77 E.02414
G1 X4.246 Y70.261 E.18506
G1 X4.246 Y70.908 E.02414
G1 X7.754 Y74.417 E.18506
G1 X7.754 Y75.064 E.02414
G1 X4.246 Y71.556 E.18506
G1 X4.246 Y72.203 E.02414
G1 X7.754 Y75.712 E.18506
G1 X7.754 Y76.359 E.02414
G1 X4.246 Y72.85 E.18506
G1 X4.246 Y73.497 E.02414
G1 X7.754 Y77.006 E.18506
G1 X7.754 Y77.653 E.02414
G1 X4.246 Y74.144 E.18506
G1 X4.246 Y74.792 E.02414
G1 X7.754 Y78.3 E.18506
G1 X7.754 Y78.948 E.02414
G1 X4.246 Y75.439 E.18506
G1 X4.246 Y76.086 E.02414
G1 X7.754 Y79.595 E.18506
G1 X7.754 Y80.242 E.02414
G1 X4.246 Y76.733 E.18506
G1 X4.246 Y77.381 E.02414
G1 X7.754 Y80.889 E.18506
G1 X7.754 Y81.537 E.02414
G1 X4.246 Y78.028 E.18506
G1 X4.246 Y78.675 E.02414
G1 X7.754 Y82.184 E.18506
G1 X7.754 Y82.831 E.02414
G1 X4.246 Y79.322 E.18506
G1 X4.246 Y79.969 E.02414
G1 X7.754 Y83.478 E.18506
G1 X7.754 Y84.125 E.02414
G1 X4.246 Y80.617 E.18506
G1 X4.246 Y81.264 E.02414
G1 X7.754 Y84.773 E.18506
G1 X7.754 Y85.42 E.02414
G1 X4.246 Y81.911 E.18506
G1 X4.246 Y82.558 E.02414
G1 X7.754 Y86.067 E.18506
G1 X7.754 Y86.714 E.02414
G1 X4.246 Y83.205 E.18506
G1 X4.246 Y83.853 E.02414
G1 X7.754 Y87.361 E.18506
G1 X7.754 Y88.009 E.02414
G1 X4.246 Y84.5 E.18506
G1 X4.246 Y85.147 E.02414
G1 X7.754 Y88.656 E.18506
G1 X7.754 Y89.303 E.02414
G1 X4.246 Y85.794 E.18506
G1 X4.246 Y86.442 E.02414
M73 P46 R11
G1 X7.754 Y89.95 E.18506
G1 X7.754 Y90.598 E.02414
G1 X4.246 Y87.089 E.18506
G1 X4.246 Y87.736 E.02414
G1 X7.754 Y91.245 E.18506
G1 X7.754 Y91.892 E.02414
G1 X4.246 Y88.383 E.18506
G1 X4.246 Y89.03 E.02414
G1 X7.754 Y92.539 E.18506
G1 X7.754 Y93.186 E.02414
G1 X4.246 Y89.678 E.18506
G1 X4.246 Y90.325 E.02414
G1 X7.754 Y93.834 E.18506
G1 X7.754 Y94.481 E.02414
G1 X4.246 Y90.972 E.18506
G1 X4.246 Y91.619 E.02414
G1 X7.754 Y95.128 E.18506
G1 X7.754 Y95.775 E.02414
G1 X4.246 Y92.266 E.18506
G1 X4.246 Y92.914 E.02414
G1 X7.754 Y96.423 E.18506
G1 X7.754 Y97.07 E.02414
G1 X4.246 Y93.561 E.18506
G1 X4.246 Y94.208 E.02414
G1 X7.754 Y97.717 E.18506
G1 X7.754 Y98.364 E.02414
G1 X4.246 Y94.855 E.18506
G1 X4.246 Y95.503 E.02414
G1 X7.754 Y99.011 E.18506
G1 X7.754 Y99.659 E.02414
G1 X4.246 Y96.15 E.18506
G1 X4.246 Y96.797 E.02414
G1 X7.754 Y100.306 E.18506
G1 X7.754 Y100.953 E.02414
G1 X4.246 Y97.444 E.18506
G1 X4.246 Y98.091 E.02414
G1 X7.754 Y101.6 E.18506
G1 X7.754 Y102.247 E.02414
G1 X4.246 Y98.739 E.18506
G1 X4.246 Y99.386 E.02414
G1 X7.754 Y102.895 E.18506
G1 X7.754 Y103.542 E.02414
G1 X4.246 Y100.033 E.18506
G1 X4.246 Y100.68 E.02414
G1 X7.754 Y104.189 E.18506
G1 X7.754 Y104.836 E.02414
G1 X4.246 Y101.327 E.18506
G1 X4.246 Y101.975 E.02414
G1 X7.754 Y105.484 E.18506
G1 X7.754 Y106.131 E.02414
G1 X4.246 Y102.622 E.18506
G1 X4.246 Y103.269 E.02414
G1 X7.754 Y106.778 E.18506
G1 X7.754 Y107.425 E.02414
G1 X4.246 Y103.916 E.18506
G1 X4.246 Y104.564 E.02414
G1 X7.754 Y108.072 E.18506
G1 X7.754 Y108.72 E.02414
G1 X4.246 Y105.211 E.18506
G1 X4.246 Y105.858 E.02414
G1 X7.754 Y109.367 E.18506
G1 X7.754 Y110.014 E.02414
G1 X4.246 Y106.505 E.18506
G1 X4.246 Y107.152 E.02414
G1 X7.754 Y110.661 E.18506
G1 X7.754 Y111.308 E.02414
G1 X4.246 Y107.8 E.18506
G1 X4.246 Y108.447 E.02414
G1 X7.754 Y111.956 E.18506
G1 X7.754 Y112.603 E.02414
G1 X4.246 Y109.094 E.18506
G1 X4.246 Y109.741 E.02414
G1 X7.754 Y113.25 E.18506
G1 X7.754 Y113.897 E.02414
G1 X4.246 Y110.388 E.18506
G1 X4.246 Y111.036 E.02414
G1 X7.754 Y114.545 E.18506
G1 X7.754 Y115.192 E.02414
G1 X4.246 Y111.683 E.18506
G1 X4.246 Y112.33 E.02414
G1 X7.754 Y115.839 E.18506
G1 X7.754 Y116.486 E.02414
G1 X4.246 Y112.977 E.18506
G1 X4.246 Y113.625 E.02414
G1 X7.754 Y117.133 E.18506
G1 X7.754 Y117.781 E.02414
G1 X4.246 Y114.272 E.18506
G1 X4.246 Y114.919 E.02414
G1 X7.754 Y118.428 E.18506
G1 X7.754 Y119.075 E.02414
G1 X4.246 Y115.566 E.18506
G1 X4.246 Y116.213 E.02414
G1 X7.754 Y119.722 E.18506
G1 X7.754 Y120.369 E.02414
G1 X4.246 Y116.861 E.18506
G1 X4.246 Y117.508 E.02414
G1 X7.754 Y121.017 E.18506
G1 X7.754 Y121.664 E.02414
G1 X4.246 Y118.155 E.18506
G1 X4.246 Y118.802 E.02414
G1 X7.754 Y122.311 E.18506
G1 X7.754 Y122.958 E.02414
G1 X4.246 Y119.449 E.18506
G1 X4.246 Y120.097 E.02414
G1 X7.754 Y123.606 E.18506
G1 X7.754 Y124.253 E.02414
G1 X4.246 Y120.744 E.18506
G1 X4.246 Y121.391 E.02414
G1 X7.754 Y124.9 E.18506
G1 X7.754 Y125.547 E.02414
G1 X4.246 Y122.038 E.18506
G1 X4.246 Y122.686 E.02414
G1 X7.754 Y126.194 E.18506
G1 X7.754 Y126.842 E.02414
G1 X4.246 Y123.333 E.18506
G1 X4.246 Y123.98 E.02414
G1 X7.754 Y127.489 E.18506
G1 X7.754 Y128.136 E.02414
G1 X4.246 Y124.627 E.18506
G1 X4.246 Y125.274 E.02414
G1 X7.754 Y128.783 E.18506
G1 X7.754 Y129.43 E.02414
M73 P47 R11
G1 X4.246 Y125.922 E.18506
G1 X4.246 Y126.569 E.02414
G1 X7.754 Y130.078 E.18506
G1 X7.754 Y130.725 E.02414
G1 X4.246 Y127.216 E.18506
G1 X4.246 Y127.863 E.02414
G1 X7.754 Y131.372 E.18506
G1 X7.754 Y132.019 E.02414
G1 X4.246 Y128.51 E.18506
G1 X4.246 Y129.158 E.02414
G1 X7.754 Y132.667 E.18506
G1 X7.754 Y133.314 E.02414
G1 X4.246 Y129.805 E.18506
G1 X4.246 Y130.452 E.02414
G1 X7.754 Y133.961 E.18506
G1 X7.754 Y134.608 E.02414
G1 X4.246 Y131.099 E.18506
G1 X4.246 Y131.747 E.02414
G1 X7.754 Y135.255 E.18506
G1 X7.754 Y135.903 E.02414
G1 X4.246 Y132.394 E.18506
G1 X4.246 Y133.041 E.02414
G1 X7.754 Y136.55 E.18506
G1 X7.754 Y137.197 E.02414
G1 X4.246 Y133.688 E.18506
G1 X4.246 Y134.335 E.02414
G1 X7.754 Y137.844 E.18506
G1 X7.754 Y138.491 E.02414
G1 X4.246 Y134.983 E.18506
G1 X4.246 Y135.63 E.02414
G1 X7.754 Y139.139 E.18506
G1 X7.754 Y139.786 E.02414
G1 X4.246 Y136.277 E.18506
G1 X4.246 Y136.924 E.02414
G1 X7.754 Y140.433 E.18506
G1 X7.754 Y141.08 E.02414
G1 X4.246 Y137.571 E.18506
G1 X4.246 Y138.219 E.02414
G1 X7.754 Y141.728 E.18506
G1 X7.754 Y142.375 E.02414
G1 X4.246 Y138.866 E.18506
G1 X4.246 Y139.513 E.02414
G1 X7.754 Y143.022 E.18506
G1 X7.754 Y143.669 E.02414
G1 X4.246 Y140.16 E.18506
G1 X4.246 Y140.808 E.02414
G1 X7.754 Y144.316 E.18506
G1 X7.754 Y144.964 E.02414
G1 X4.246 Y141.455 E.18506
G1 X4.246 Y142.102 E.02414
G1 X7.754 Y145.611 E.18506
G1 X7.754 Y146.258 E.02414
G1 X4.246 Y142.749 E.18506
G1 X4.246 Y143.396 E.02414
G1 X7.754 Y146.905 E.18506
G1 X7.754 Y147.552 E.02414
G1 X4.246 Y144.044 E.18506
G1 X4.246 Y144.691 E.02414
G1 X7.754 Y148.2 E.18506
G1 X7.754 Y148.847 E.02414
G1 X4.246 Y145.338 E.18506
G1 X4.246 Y145.985 E.02414
G1 X7.754 Y149.494 E.18506
G1 X7.754 Y150.141 E.02414
G1 X4.246 Y146.632 E.18506
G1 X4.246 Y147.28 E.02414
G1 X7.754 Y150.789 E.18506
G1 X7.754 Y151.436 E.02414
G1 X4.246 Y147.927 E.18506
G1 X4.246 Y148.574 E.02414
G1 X7.754 Y152.083 E.18506
G1 X7.754 Y152.73 E.02414
G1 X4.246 Y149.221 E.18506
G1 X4.246 Y149.869 E.02414
G1 X7.754 Y153.377 E.18506
G1 X7.754 Y154.025 E.02414
G1 X4.246 Y150.516 E.18506
G1 X4.246 Y151.163 E.02414
G1 X7.754 Y154.672 E.18506
G1 X7.754 Y155.319 E.02414
G1 X4.246 Y151.81 E.18506
G1 X4.246 Y152.457 E.02414
G1 X7.754 Y155.966 E.18506
G1 X7.754 Y156.613 E.02414
G1 X4.246 Y153.105 E.18506
G1 X4.246 Y153.752 E.02414
G1 X7.754 Y157.261 E.18506
G1 X7.754 Y157.908 E.02414
G1 X4.246 Y154.399 E.18506
G1 X4.246 Y155.046 E.02414
G1 X7.754 Y158.555 E.18506
G1 X7.754 Y159.202 E.02414
G1 X4.246 Y155.694 E.18506
G1 X4.246 Y156.341 E.02414
G1 X7.754 Y159.85 E.18506
G1 X7.754 Y160.497 E.02414
G1 X4.246 Y156.988 E.18506
G1 X4.246 Y157.635 E.02414
G1 X7.754 Y161.144 E.18506
G1 X7.754 Y161.791 E.02414
G1 X4.246 Y158.282 E.18506
G1 X4.246 Y158.93 E.02414
G1 X7.754 Y162.438 E.18506
G1 X7.754 Y163.086 E.02414
G1 X4.246 Y159.577 E.18506
G1 X4.246 Y160.224 E.02414
G1 X7.754 Y163.733 E.18506
G1 X7.754 Y164.38 E.02414
G1 X4.246 Y160.871 E.18506
G1 X4.246 Y161.518 E.02414
G1 X7.754 Y165.027 E.18506
G1 X7.754 Y165.674 E.02414
G1 X4.246 Y162.166 E.18506
G1 X4.246 Y162.813 E.02414
G1 X7.754 Y166.322 E.18506
G1 X7.754 Y166.969 E.02414
G1 X4.246 Y163.46 E.18506
G1 X4.246 Y164.107 E.02414
G1 X7.754 Y167.616 E.18506
G1 X7.754 Y168.263 E.02414
G1 X4.246 Y164.755 E.18506
G1 X4.246 Y165.402 E.02414
M73 P48 R11
G1 X7.754 Y168.911 E.18506
G1 X7.754 Y169.558 E.02414
G1 X4.246 Y166.049 E.18506
G1 X4.246 Y166.696 E.02414
G1 X7.754 Y170.205 E.18506
G1 X7.754 Y170.852 E.02414
G1 X4.246 Y167.343 E.18506
G1 X4.246 Y167.991 E.02414
G1 X7.754 Y171.499 E.18506
G1 X7.754 Y172.147 E.02414
G1 X4.246 Y168.638 E.18506
G1 X4.246 Y169.285 E.02414
G1 X7.754 Y172.794 E.18506
G1 X7.754 Y173.441 E.02414
G1 X4.246 Y169.932 E.18506
G1 X4.246 Y170.579 E.02414
G1 X7.754 Y174.088 E.18506
G1 X7.754 Y174.736 E.02414
G1 X4.246 Y171.227 E.18506
G1 X4.246 Y171.874 E.02414
G1 X7.754 Y175.383 E.18506
G1 X7.754 Y176.03 E.02414
G1 X4.246 Y172.521 E.18506
G1 X4.246 Y173.168 E.02414
G1 X7.754 Y176.677 E.18506
G1 X7.754 Y177.324 E.02414
G1 X4.246 Y173.816 E.18506
G1 X4.246 Y174.463 E.02414
G1 X7.754 Y177.972 E.18506
G1 X7.754 Y178.619 E.02414
G1 X4.246 Y175.11 E.18506
G1 X4.246 Y175.757 E.02414
G1 X7.754 Y179.266 E.18506
G1 X7.754 Y179.913 E.02414
G1 X4.246 Y176.404 E.18506
G1 X4.246 Y177.052 E.02414
G1 X7.754 Y180.56 E.18506
G1 X7.754 Y181.208 E.02414
G1 X4.246 Y177.699 E.18506
G1 X4.246 Y178.346 E.02414
G1 X7.754 Y181.855 E.18506
G1 X7.754 Y182.502 E.02414
G1 X4.246 Y178.993 E.18506
G1 X4.246 Y179.64 E.02414
G1 X7.754 Y183.149 E.18506
G1 X7.754 Y183.797 E.02414
G1 X4.246 Y180.288 E.18506
G1 X4.246 Y180.935 E.02414
G1 X7.754 Y184.444 E.18506
G1 X7.754 Y185.091 E.02414
G1 X4.246 Y181.582 E.18506
G1 X4.246 Y182.229 E.02414
G1 X7.754 Y185.738 E.18506
G1 X7.754 Y186.385 E.02414
G1 X4.246 Y182.877 E.18506
G1 X4.246 Y183.524 E.02414
G1 X7.754 Y187.033 E.18506
G1 X7.754 Y187.68 E.02414
G1 X4.246 Y184.171 E.18506
G1 X4.246 Y184.818 E.02414
G1 X7.754 Y188.327 E.18506
G1 X7.754 Y188.974 E.02414
G1 X4.246 Y185.465 E.18506
G1 X4.246 Y186.113 E.02414
G1 X7.754 Y189.621 E.18506
G1 X7.754 Y190.269 E.02414
G1 X4.246 Y186.76 E.18506
G1 X4.246 Y187.407 E.02414
G1 X7.754 Y190.916 E.18506
G1 X7.754 Y191.563 E.02414
G1 X4.246 Y188.054 E.18506
G1 X4.246 Y188.701 E.02414
G1 X7.754 Y192.21 E.18506
G1 X7.754 Y192.858 E.02414
G1 X4.246 Y189.349 E.18506
G1 X4.246 Y189.996 E.02414
G1 X7.754 Y193.505 E.18506
G1 X7.754 Y194.152 E.02414
G1 X4.246 Y190.643 E.18506
G1 X4.246 Y191.29 E.02414
G1 X7.754 Y194.799 E.18506
G1 X7.754 Y195.446 E.02414
G1 X4.246 Y191.938 E.18506
G1 X4.246 Y192.585 E.02414
G1 X7.754 Y196.094 E.18506
G1 X7.754 Y196.741 E.02414
G1 X4.246 Y193.232 E.18506
G1 X4.246 Y193.879 E.02414
G1 X7.754 Y197.388 E.18506
G1 X7.754 Y198.035 E.02414
G1 X4.246 Y194.526 E.18506
G1 X4.246 Y195.174 E.02414
G1 X7.754 Y198.682 E.18506
G1 X7.754 Y199.33 E.02414
G1 X4.246 Y195.821 E.18506
G1 X4.246 Y196.468 E.02414
G1 X7.754 Y199.977 E.18506
G1 X7.754 Y200.624 E.02414
G1 X4.246 Y197.115 E.18506
G1 X4.246 Y197.762 E.02414
G1 X7.754 Y201.271 E.18506
G1 X7.754 Y201.919 E.02414
G1 X4.246 Y198.41 E.18506
G1 X4.246 Y199.057 E.02414
G1 X7.754 Y202.566 E.18506
G1 X7.754 Y203.213 E.02414
G1 X4.246 Y199.704 E.18506
G1 X4.246 Y200.351 E.02414
G1 X7.754 Y203.86 E.18506
G1 X7.754 Y204.507 E.02414
G1 X4.246 Y200.999 E.18506
G1 X4.246 Y201.646 E.02414
G1 X7.754 Y205.155 E.18506
G1 X7.754 Y205.802 E.02414
G1 X4.246 Y202.293 E.18506
G1 X4.246 Y202.94 E.02414
G1 X7.754 Y206.449 E.18506
G1 X7.754 Y207.096 E.02414
G1 X4.246 Y203.587 E.18506
G1 X4.246 Y204.235 E.02414
G1 X7.754 Y207.743 E.18506
M73 P49 R11
G1 X7.754 Y208.391 E.02414
G1 X4.246 Y204.882 E.18506
G1 X4.246 Y205.529 E.02414
M73 P49 R10
G1 X7.754 Y209.038 E.18506
G1 X7.754 Y209.685 E.02414
G1 X4.246 Y206.176 E.18506
G1 X4.246 Y206.823 E.02414
G1 X7.754 Y210.332 E.18506
G1 X7.754 Y210.98 E.02414
G1 X4.246 Y207.471 E.18506
G1 X4.246 Y208.118 E.02414
G1 X7.754 Y211.627 E.18506
G1 X7.754 Y212.274 E.02414
G1 X4.246 Y208.765 E.18506
G1 X4.246 Y209.412 E.02414
G1 X7.754 Y212.921 E.18506
G1 X7.754 Y213.568 E.02414
G1 X4.246 Y210.06 E.18506
G1 X4.246 Y210.707 E.02414
G1 X7.754 Y214.216 E.18506
G1 X7.754 Y214.863 E.02414
G1 X4.246 Y211.354 E.18506
G1 X4.246 Y212.001 E.02414
G1 X7.754 Y215.51 E.18506
G1 X7.754 Y216.157 E.02414
G1 X4.246 Y212.648 E.18506
G1 X4.246 Y213.296 E.02414
G1 X7.754 Y216.804 E.18506
G1 X7.754 Y217.452 E.02414
G1 X4.246 Y213.943 E.18506
G1 X4.246 Y214.59 E.02414
G1 X7.754 Y218.099 E.18506
G1 X7.754 Y218.746 E.02414
G1 X4.246 Y215.237 E.18506
G1 X4.246 Y215.884 E.02414
G1 X7.754 Y219.393 E.18506
G1 X7.754 Y220.041 E.02414
G1 X4.246 Y216.532 E.18506
G1 X4.246 Y217.179 E.02414
G1 X7.754 Y220.688 E.18506
G1 X7.754 Y221.335 E.02414
G1 X4.246 Y217.826 E.18506
G1 X4.246 Y218.473 E.02414
G1 X7.96 Y222.188 E.1959
; WIPE_START
G1 X6.546 Y220.774 E-.76
; WIPE_END
G1 E-.04 F1800
M204 S6000
G1 X12.581 Y216.101 Z.6 F36000
G1 X248.04 Y33.811 Z.6
G1 Z.2
G1 E.8 F1800
G1 F6300
M204 S500
G1 X251.754 Y37.526 E.1959
G1 X251.754 Y38.173 E.02414
G1 X248.246 Y34.664 E.18506
G1 X248.246 Y35.312 E.02414
G1 X251.754 Y38.82 E.18506
G1 X251.754 Y39.468 E.02414
G1 X248.246 Y35.959 E.18506
G1 X248.246 Y36.606 E.02414
G1 X251.754 Y40.115 E.18506
G1 X251.754 Y40.762 E.02414
G1 X248.246 Y37.253 E.18506
G1 X248.246 Y37.9 E.02414
G1 X251.754 Y41.409 E.18506
G1 X251.754 Y42.056 E.02414
G1 X248.246 Y38.548 E.18506
G1 X248.246 Y39.195 E.02414
G1 X251.754 Y42.704 E.18506
G1 X251.754 Y43.351 E.02414
G1 X248.246 Y39.842 E.18506
G1 X248.246 Y40.489 E.02414
G1 X251.754 Y43.998 E.18506
G1 X251.754 Y44.645 E.02414
G1 X248.246 Y41.136 E.18506
G1 X248.246 Y41.784 E.02414
G1 X251.754 Y45.293 E.18506
G1 X251.754 Y45.94 E.02414
G1 X248.246 Y42.431 E.18506
G1 X248.246 Y43.078 E.02414
G1 X251.754 Y46.587 E.18506
G1 X251.754 Y47.234 E.02414
G1 X248.246 Y43.725 E.18506
G1 X248.246 Y44.373 E.02414
G1 X251.754 Y47.881 E.18506
G1 X251.754 Y48.529 E.02414
G1 X248.246 Y45.02 E.18506
G1 X248.246 Y45.667 E.02414
G1 X251.754 Y49.176 E.18506
G1 X251.754 Y49.823 E.02414
G1 X248.246 Y46.314 E.18506
G1 X248.246 Y46.961 E.02414
G1 X251.754 Y50.47 E.18506
G1 X251.754 Y51.117 E.02414
G1 X248.246 Y47.609 E.18506
G1 X248.246 Y48.256 E.02414
G1 X251.754 Y51.765 E.18506
G1 X251.754 Y52.412 E.02414
G1 X248.246 Y48.903 E.18506
G1 X248.246 Y49.55 E.02414
G1 X251.754 Y53.059 E.18506
G1 X251.754 Y53.706 E.02414
G1 X248.246 Y50.197 E.18506
G1 X248.246 Y50.845 E.02414
G1 X251.754 Y54.354 E.18506
G1 X251.754 Y55.001 E.02414
G1 X248.246 Y51.492 E.18506
G1 X248.246 Y52.139 E.02414
G1 X251.754 Y55.648 E.18506
G1 X251.754 Y56.295 E.02414
G1 X248.246 Y52.786 E.18506
G1 X248.246 Y53.434 E.02414
G1 X251.754 Y56.942 E.18506
G1 X251.754 Y57.59 E.02414
G1 X248.246 Y54.081 E.18506
G1 X248.246 Y54.728 E.02414
G1 X251.754 Y58.237 E.18506
G1 X251.754 Y58.884 E.02414
G1 X248.246 Y55.375 E.18506
G1 X248.246 Y56.022 E.02414
G1 X251.754 Y59.531 E.18506
M73 P50 R10
G1 X251.754 Y60.178 E.02414
G1 X248.246 Y56.67 E.18506
G1 X248.246 Y57.317 E.02414
G1 X251.754 Y60.826 E.18506
G1 X251.754 Y61.473 E.02414
G1 X248.246 Y57.964 E.18506
G1 X248.246 Y58.611 E.02414
G1 X251.754 Y62.12 E.18506
G1 X251.754 Y62.767 E.02414
G1 X248.246 Y59.259 E.18506
G1 X248.246 Y59.906 E.02414
G1 X251.754 Y63.415 E.18506
G1 X251.754 Y64.062 E.02414
G1 X248.246 Y60.553 E.18506
G1 X248.246 Y61.2 E.02414
G1 X251.754 Y64.709 E.18506
G1 X251.754 Y65.356 E.02414
G1 X248.246 Y61.847 E.18506
G1 X248.246 Y62.495 E.02414
G1 X251.754 Y66.003 E.18506
G1 X251.754 Y66.651 E.02414
G1 X248.246 Y63.142 E.18506
G1 X248.246 Y63.789 E.02414
G1 X251.754 Y67.298 E.18506
G1 X251.754 Y67.945 E.02414
G1 X248.246 Y64.436 E.18506
G1 X248.246 Y65.083 E.02414
G1 X251.754 Y68.592 E.18506
G1 X251.754 Y69.239 E.02414
G1 X248.246 Y65.731 E.18506
G1 X248.246 Y66.378 E.02414
G1 X251.754 Y69.887 E.18506
G1 X251.754 Y70.534 E.02414
G1 X248.246 Y67.025 E.18506
G1 X248.246 Y67.672 E.02414
G1 X251.754 Y71.181 E.18506
G1 X251.754 Y71.828 E.02414
G1 X248.246 Y68.32 E.18506
G1 X248.246 Y68.967 E.02414
G1 X251.754 Y72.476 E.18506
G1 X251.754 Y73.123 E.02414
G1 X248.246 Y69.614 E.18506
G1 X248.246 Y70.261 E.02414
G1 X251.754 Y73.77 E.18506
G1 X251.754 Y74.417 E.02414
G1 X248.246 Y70.908 E.18506
G1 X248.246 Y71.556 E.02414
G1 X251.754 Y75.064 E.18506
G1 X251.754 Y75.712 E.02414
G1 X248.246 Y72.203 E.18506
G1 X248.246 Y72.85 E.02414
G1 X251.754 Y76.359 E.18506
G1 X251.754 Y77.006 E.02414
G1 X248.246 Y73.497 E.18506
G1 X248.246 Y74.144 E.02414
G1 X251.754 Y77.653 E.18506
G1 X251.754 Y78.301 E.02414
G1 X248.246 Y74.792 E.18506
G1 X248.246 Y75.439 E.02414
G1 X251.754 Y78.948 E.18506
G1 X251.754 Y79.595 E.02414
G1 X248.246 Y76.086 E.18506
G1 X248.246 Y76.733 E.02414
G1 X251.754 Y80.242 E.18506
G1 X251.754 Y80.889 E.02414
G1 X248.246 Y77.381 E.18506
G1 X248.246 Y78.028 E.02414
G1 X251.754 Y81.537 E.18506
G1 X251.754 Y82.184 E.02414
G1 X248.246 Y78.675 E.18506
G1 X248.246 Y79.322 E.02414
G1 X251.754 Y82.831 E.18506
G1 X251.754 Y83.478 E.02414
G1 X248.246 Y79.969 E.18506
G1 X248.246 Y80.617 E.02414
G1 X251.754 Y84.125 E.18506
G1 X251.754 Y84.773 E.02414
G1 X248.246 Y81.264 E.18506
G1 X248.246 Y81.911 E.02414
G1 X251.754 Y85.42 E.18506
G1 X251.754 Y86.067 E.02414
G1 X248.246 Y82.558 E.18506
G1 X248.246 Y83.205 E.02414
G1 X251.754 Y86.714 E.18506
G1 X251.754 Y87.362 E.02414
G1 X248.246 Y83.853 E.18506
G1 X248.246 Y84.5 E.02414
G1 X251.754 Y88.009 E.18506
G1 X251.754 Y88.656 E.02414
G1 X248.246 Y85.147 E.18506
G1 X248.246 Y85.794 E.02414
G1 X251.754 Y89.303 E.18506
G1 X251.754 Y89.95 E.02414
G1 X248.246 Y86.442 E.18506
G1 X248.246 Y87.089 E.02414
G1 X251.754 Y90.598 E.18506
G1 X251.754 Y91.245 E.02414
G1 X248.246 Y87.736 E.18506
G1 X248.246 Y88.383 E.02414
G1 X251.754 Y91.892 E.18506
G1 X251.754 Y92.539 E.02414
G1 X248.246 Y89.03 E.18506
G1 X248.246 Y89.678 E.02414
G1 X251.754 Y93.186 E.18506
G1 X251.754 Y93.834 E.02414
G1 X248.246 Y90.325 E.18506
G1 X248.246 Y90.972 E.02414
G1 X251.754 Y94.481 E.18506
G1 X251.754 Y95.128 E.02414
G1 X248.246 Y91.619 E.18506
G1 X248.246 Y92.266 E.02414
G1 X251.754 Y95.775 E.18506
G1 X251.754 Y96.423 E.02414
G1 X248.246 Y92.914 E.18506
G1 X248.246 Y93.561 E.02414
G1 X251.754 Y97.07 E.18506
G1 X251.754 Y97.717 E.02414
G1 X248.246 Y94.208 E.18506
G1 X248.246 Y94.855 E.02414
G1 X251.754 Y98.364 E.18506
G1 X251.754 Y99.011 E.02414
M73 P51 R10
G1 X248.246 Y95.503 E.18506
G1 X248.246 Y96.15 E.02414
G1 X251.754 Y99.659 E.18506
G1 X251.754 Y100.306 E.02414
G1 X248.246 Y96.797 E.18506
G1 X248.246 Y97.444 E.02414
G1 X251.754 Y100.953 E.18506
G1 X251.754 Y101.6 E.02414
G1 X248.246 Y98.091 E.18506
G1 X248.246 Y98.739 E.02414
G1 X251.754 Y102.247 E.18506
G1 X251.754 Y102.895 E.02414
G1 X248.246 Y99.386 E.18506
G1 X248.246 Y100.033 E.02414
G1 X251.754 Y103.542 E.18506
G1 X251.754 Y104.189 E.02414
G1 X248.246 Y100.68 E.18506
G1 X248.246 Y101.327 E.02414
G1 X251.754 Y104.836 E.18506
G1 X251.754 Y105.484 E.02414
G1 X248.246 Y101.975 E.18506
G1 X248.246 Y102.622 E.02414
G1 X251.754 Y106.131 E.18506
G1 X251.754 Y106.778 E.02414
G1 X248.246 Y103.269 E.18506
G1 X248.246 Y103.916 E.02414
G1 X251.754 Y107.425 E.18506
G1 X251.754 Y108.072 E.02414
G1 X248.246 Y104.564 E.18506
G1 X248.246 Y105.211 E.02414
G1 X251.754 Y108.72 E.18506
G1 X251.754 Y109.367 E.02414
G1 X248.246 Y105.858 E.18506
G1 X248.246 Y106.505 E.02414
G1 X251.754 Y110.014 E.18506
G1 X251.754 Y110.661 E.02414
G1 X248.246 Y107.152 E.18506
G1 X248.246 Y107.8 E.02414
G1 X251.754 Y111.308 E.18506
G1 X251.754 Y111.956 E.02414
G1 X248.246 Y108.447 E.18506
G1 X248.246 Y109.094 E.02414
G1 X251.754 Y112.603 E.18506
G1 X251.754 Y113.25 E.02414
G1 X248.246 Y109.741 E.18506
G1 X248.246 Y110.388 E.02414
G1 X251.754 Y113.897 E.18506
G1 X251.754 Y114.545 E.02414
G1 X248.246 Y111.036 E.18506
G1 X248.246 Y111.683 E.02414
G1 X251.754 Y115.192 E.18506
G1 X251.754 Y115.839 E.02414
G1 X248.246 Y112.33 E.18506
G1 X248.246 Y112.977 E.02414
G1 X251.754 Y116.486 E.18506
G1 X251.754 Y117.133 E.02414
G1 X248.246 Y113.625 E.18506
G1 X248.246 Y114.272 E.02414
G1 X251.754 Y117.781 E.18506
G1 X251.754 Y118.428 E.02414
G1 X248.246 Y114.919 E.18506
G1 X248.246 Y115.566 E.02414
G1 X251.754 Y119.075 E.18506
G1 X251.754 Y119.722 E.02414
G1 X248.246 Y116.213 E.18506
G1 X248.246 Y116.861 E.02414
G1 X251.754 Y120.369 E.18506
G1 X251.754 Y121.017 E.02414
G1 X248.246 Y117.508 E.18506
G1 X248.246 Y118.155 E.02414
G1 X251.754 Y121.664 E.18506
G1 X251.754 Y122.311 E.02414
G1 X248.246 Y118.802 E.18506
G1 X248.246 Y119.449 E.02414
G1 X251.754 Y122.958 E.18506
G1 X251.754 Y123.606 E.02414
G1 X248.246 Y120.097 E.18506
G1 X248.246 Y120.744 E.02414
G1 X251.754 Y124.253 E.18506
G1 X251.754 Y124.9 E.02414
G1 X248.246 Y121.391 E.18506
G1 X248.246 Y122.038 E.02414
G1 X251.754 Y125.547 E.18506
G1 X251.754 Y126.194 E.02414
G1 X248.246 Y122.686 E.18506
G1 X248.246 Y123.333 E.02414
G1 X251.754 Y126.842 E.18506
G1 X251.754 Y127.489 E.02414
G1 X248.246 Y123.98 E.18506
G1 X248.246 Y124.627 E.02414
G1 X251.754 Y128.136 E.18506
G1 X251.754 Y128.783 E.02414
G1 X248.246 Y125.274 E.18506
G1 X248.246 Y125.922 E.02414
G1 X251.754 Y129.43 E.18506
G1 X251.754 Y130.078 E.02414
G1 X248.246 Y126.569 E.18506
G1 X248.246 Y127.216 E.02414
G1 X251.754 Y130.725 E.18506
G1 X251.754 Y131.372 E.02414
G1 X248.246 Y127.863 E.18506
G1 X248.246 Y128.51 E.02414
G1 X251.754 Y132.019 E.18506
G1 X251.754 Y132.667 E.02414
G1 X248.246 Y129.158 E.18506
G1 X248.246 Y129.805 E.02414
G1 X251.754 Y133.314 E.18506
G1 X251.754 Y133.961 E.02414
G1 X248.246 Y130.452 E.18506
G1 X248.246 Y131.099 E.02414
G1 X251.754 Y134.608 E.18506
G1 X251.754 Y135.255 E.02414
G1 X248.246 Y131.747 E.18506
G1 X248.246 Y132.394 E.02414
G1 X251.754 Y135.903 E.18506
G1 X251.754 Y136.55 E.02414
G1 X248.246 Y133.041 E.18506
G1 X248.246 Y133.688 E.02414
G1 X251.754 Y137.197 E.18506
G1 X251.754 Y137.844 E.02414
G1 X248.246 Y134.335 E.18506
G1 X248.246 Y134.983 E.02414
M73 P52 R10
G1 X251.754 Y138.491 E.18506
G1 X251.754 Y139.139 E.02414
G1 X248.246 Y135.63 E.18506
G1 X248.246 Y136.277 E.02414
G1 X251.754 Y139.786 E.18506
G1 X251.754 Y140.433 E.02414
G1 X248.246 Y136.924 E.18506
G1 X248.246 Y137.571 E.02414
G1 X251.754 Y141.08 E.18506
G1 X251.754 Y141.728 E.02414
G1 X248.246 Y138.219 E.18506
G1 X248.246 Y138.866 E.02414
G1 X251.754 Y142.375 E.18506
G1 X251.754 Y143.022 E.02414
G1 X248.246 Y139.513 E.18506
G1 X248.246 Y140.16 E.02414
G1 X251.754 Y143.669 E.18506
G1 X251.754 Y144.316 E.02414
G1 X248.246 Y140.808 E.18506
G1 X248.246 Y141.455 E.02414
G1 X251.754 Y144.964 E.18506
G1 X251.754 Y145.611 E.02414
G1 X248.246 Y142.102 E.18506
G1 X248.246 Y142.749 E.02414
G1 X251.754 Y146.258 E.18506
G1 X251.754 Y146.905 E.02414
G1 X248.246 Y143.396 E.18506
G1 X248.246 Y144.044 E.02414
G1 X251.754 Y147.552 E.18506
G1 X251.754 Y148.2 E.02414
G1 X248.246 Y144.691 E.18506
G1 X248.246 Y145.338 E.02414
G1 X251.754 Y148.847 E.18506
G1 X251.754 Y149.494 E.02414
G1 X248.246 Y145.985 E.18506
G1 X248.246 Y146.633 E.02414
G1 X251.754 Y150.141 E.18506
G1 X251.754 Y150.789 E.02414
G1 X248.246 Y147.28 E.18506
G1 X248.246 Y147.927 E.02414
G1 X251.754 Y151.436 E.18506
G1 X251.754 Y152.083 E.02414
G1 X248.246 Y148.574 E.18506
G1 X248.246 Y149.221 E.02414
G1 X251.754 Y152.73 E.18506
G1 X251.754 Y153.377 E.02414
G1 X248.246 Y149.869 E.18506
G1 X248.246 Y150.516 E.02414
G1 X251.754 Y154.025 E.18506
G1 X251.754 Y154.672 E.02414
G1 X248.246 Y151.163 E.18506
G1 X248.246 Y151.81 E.02414
G1 X251.754 Y155.319 E.18506
G1 X251.754 Y155.966 E.02414
G1 X248.246 Y152.457 E.18506
G1 X248.246 Y153.105 E.02414
G1 X251.754 Y156.613 E.18506
G1 X251.754 Y157.261 E.02414
G1 X248.246 Y153.752 E.18506
G1 X248.246 Y154.399 E.02414
G1 X251.754 Y157.908 E.18506
G1 X251.754 Y158.555 E.02414
G1 X248.246 Y155.046 E.18506
G1 X248.246 Y155.694 E.02414
G1 X251.754 Y159.202 E.18506
G1 X251.754 Y159.85 E.02414
G1 X248.246 Y156.341 E.18506
G1 X248.246 Y156.988 E.02414
G1 X251.754 Y160.497 E.18506
G1 X251.754 Y161.144 E.02414
G1 X248.246 Y157.635 E.18506
G1 X248.246 Y158.282 E.02414
G1 X251.754 Y161.791 E.18506
G1 X251.754 Y162.438 E.02414
G1 X248.246 Y158.93 E.18506
G1 X248.246 Y159.577 E.02414
G1 X251.754 Y163.086 E.18506
G1 X251.754 Y163.733 E.02414
G1 X248.246 Y160.224 E.18506
G1 X248.246 Y160.871 E.02414
G1 X251.754 Y164.38 E.18506
G1 X251.754 Y165.027 E.02414
G1 X248.246 Y161.518 E.18506
G1 X248.246 Y162.166 E.02414
G1 X251.754 Y165.675 E.18506
G1 X251.754 Y166.322 E.02414
G1 X248.246 Y162.813 E.18506
G1 X248.246 Y163.46 E.02414
G1 X251.754 Y166.969 E.18506
G1 X251.754 Y167.616 E.02414
G1 X248.246 Y164.107 E.18506
G1 X248.246 Y164.755 E.02414
G1 X251.754 Y168.263 E.18506
G1 X251.754 Y168.911 E.02414
G1 X248.246 Y165.402 E.18506
G1 X248.246 Y166.049 E.02414
G1 X251.754 Y169.558 E.18506
G1 X251.754 Y170.205 E.02414
G1 X248.246 Y166.696 E.18506
G1 X248.246 Y167.343 E.02414
G1 X251.754 Y170.852 E.18506
G1 X251.754 Y171.499 E.02414
G1 X248.246 Y167.991 E.18506
G1 X248.246 Y168.638 E.02414
G1 X251.754 Y172.147 E.18506
G1 X251.754 Y172.794 E.02414
G1 X248.246 Y169.285 E.18506
G1 X248.246 Y169.932 E.02414
G1 X251.754 Y173.441 E.18506
G1 X251.754 Y174.088 E.02414
G1 X248.246 Y170.579 E.18506
G1 X248.246 Y171.227 E.02414
G1 X251.754 Y174.736 E.18506
G1 X251.754 Y175.383 E.02414
G1 X248.246 Y171.874 E.18506
G1 X248.246 Y172.521 E.02414
G1 X251.754 Y176.03 E.18506
G1 X251.754 Y176.677 E.02414
G1 X248.246 Y173.168 E.18506
G1 X248.246 Y173.816 E.02414
G1 X251.754 Y177.324 E.18506
G1 X251.754 Y177.972 E.02414
M73 P53 R10
G1 X248.246 Y174.463 E.18506
G1 X248.246 Y175.11 E.02414
G1 X251.754 Y178.619 E.18506
G1 X251.754 Y179.266 E.02414
G1 X248.246 Y175.757 E.18506
G1 X248.246 Y176.404 E.02414
G1 X251.754 Y179.913 E.18506
G1 X251.754 Y180.56 E.02414
G1 X248.246 Y177.052 E.18506
G1 X248.246 Y177.699 E.02414
G1 X251.754 Y181.208 E.18506
G1 X251.754 Y181.855 E.02414
G1 X248.246 Y178.346 E.18506
G1 X248.246 Y178.993 E.02414
G1 X251.754 Y182.502 E.18506
G1 X251.754 Y183.149 E.02414
G1 X248.246 Y179.64 E.18506
G1 X248.246 Y180.288 E.02414
G1 X251.754 Y183.797 E.18506
G1 X251.754 Y184.444 E.02414
G1 X248.246 Y180.935 E.18506
G1 X248.246 Y181.582 E.02414
G1 X251.754 Y185.091 E.18506
G1 X251.754 Y185.738 E.02414
G1 X248.246 Y182.229 E.18506
G1 X248.246 Y182.877 E.02414
G1 X251.754 Y186.385 E.18506
G1 X251.754 Y187.033 E.02414
G1 X248.246 Y183.524 E.18506
G1 X248.246 Y184.171 E.02414
G1 X251.754 Y187.68 E.18506
G1 X251.754 Y188.327 E.02414
G1 X248.246 Y184.818 E.18506
G1 X248.246 Y185.465 E.02414
G1 X251.754 Y188.974 E.18506
G1 X251.754 Y189.621 E.02414
G1 X248.246 Y186.113 E.18506
G1 X248.246 Y186.76 E.02414
G1 X251.754 Y190.269 E.18506
G1 X251.754 Y190.916 E.02414
G1 X248.246 Y187.407 E.18506
G1 X248.246 Y188.054 E.02414
G1 X251.754 Y191.563 E.18506
G1 X251.754 Y192.21 E.02414
G1 X248.246 Y188.701 E.18506
G1 X248.246 Y189.349 E.02414
G1 X251.754 Y192.858 E.18506
G1 X251.754 Y193.505 E.02414
G1 X248.246 Y189.996 E.18506
G1 X248.246 Y190.643 E.02414
G1 X251.754 Y194.152 E.18506
G1 X251.754 Y194.799 E.02414
G1 X248.246 Y191.29 E.18506
G1 X248.246 Y191.938 E.02414
G1 X251.754 Y195.446 E.18506
G1 X251.754 Y196.094 E.02414
G1 X248.246 Y192.585 E.18506
G1 X248.246 Y193.232 E.02414
G1 X251.754 Y196.741 E.18506
G1 X251.754 Y197.388 E.02414
G1 X248.246 Y193.879 E.18506
G1 X248.246 Y194.526 E.02414
G1 X251.754 Y198.035 E.18506
G1 X251.754 Y198.682 E.02414
G1 X248.246 Y195.174 E.18506
G1 X248.246 Y195.821 E.02414
G1 X251.754 Y199.33 E.18506
G1 X251.754 Y199.977 E.02414
G1 X248.246 Y196.468 E.18506
G1 X248.246 Y197.115 E.02414
G1 X251.754 Y200.624 E.18506
G1 X251.754 Y201.271 E.02414
G1 X248.246 Y197.762 E.18506
G1 X248.246 Y198.41 E.02414
G1 X251.754 Y201.919 E.18506
G1 X251.754 Y202.566 E.02414
G1 X248.246 Y199.057 E.18506
G1 X248.246 Y199.704 E.02414
G1 X251.754 Y203.213 E.18506
G1 X251.754 Y203.86 E.02414
M73 P53 R9
G1 X248.246 Y200.351 E.18506
G1 X248.246 Y200.999 E.02414
G1 X251.754 Y204.507 E.18506
G1 X251.754 Y205.155 E.02414
G1 X248.246 Y201.646 E.18506
G1 X248.246 Y202.293 E.02414
G1 X251.754 Y205.802 E.18506
G1 X251.754 Y206.449 E.02414
G1 X248.246 Y202.94 E.18506
G1 X248.246 Y203.587 E.02414
G1 X251.754 Y207.096 E.18506
G1 X251.754 Y207.743 E.02414
G1 X248.246 Y204.235 E.18506
G1 X248.246 Y204.882 E.02414
G1 X251.754 Y208.391 E.18506
G1 X251.754 Y209.038 E.02414
G1 X248.246 Y205.529 E.18506
G1 X248.246 Y206.176 E.02414
G1 X251.754 Y209.685 E.18506
G1 X251.754 Y210.332 E.02414
G1 X248.246 Y206.823 E.18506
G1 X248.246 Y207.471 E.02414
G1 X251.754 Y210.98 E.18506
G1 X251.754 Y211.627 E.02414
G1 X248.246 Y208.118 E.18506
G1 X248.246 Y208.765 E.02414
G1 X251.754 Y212.274 E.18506
G1 X251.754 Y212.921 E.02414
G1 X248.246 Y209.412 E.18506
G1 X248.246 Y210.06 E.02414
G1 X251.754 Y213.568 E.18506
G1 X251.754 Y214.216 E.02414
G1 X248.246 Y210.707 E.18506
G1 X248.246 Y211.354 E.02414
G1 X251.754 Y214.863 E.18506
G1 X251.754 Y215.51 E.02414
G1 X248.246 Y212.001 E.18506
G1 X248.246 Y212.648 E.02414
G1 X251.754 Y216.157 E.18506
G1 X251.754 Y216.804 E.02414
G1 X248.246 Y213.296 E.18506
G1 X248.246 Y213.943 E.02414
M73 P54 R9
G1 X251.754 Y217.452 E.18506
G1 X251.754 Y218.099 E.02414
G1 X248.246 Y214.59 E.18506
G1 X248.246 Y215.237 E.02414
G1 X251.754 Y218.746 E.18506
G1 X251.754 Y219.393 E.02414
G1 X248.246 Y215.884 E.18506
G1 X248.246 Y216.532 E.02414
G1 X251.754 Y220.041 E.18506
G1 X251.754 Y220.688 E.02414
G1 X248.246 Y217.179 E.18506
G1 X248.246 Y217.826 E.02414
G1 X251.754 Y221.335 E.18506
G1 X251.754 Y221.982 E.02414
G1 X248.246 Y218.473 E.18506
G1 X248.246 Y219.121 E.02414
G1 X251.754 Y222.629 E.18506
G1 X251.754 Y223.277 E.02414
G1 X248.246 Y219.768 E.18506
G1 X248.246 Y220.415 E.02414
G1 X251.754 Y223.924 E.18506
G1 X251.754 Y224.571 E.02414
G1 X248.246 Y221.062 E.18506
G1 X248.246 Y221.709 E.02414
G1 X251.754 Y225.218 E.18506
G1 X251.754 Y225.865 E.02414
G1 X248.246 Y222.357 E.18506
G1 X248.246 Y223.004 E.02414
G1 X251.754 Y226.513 E.18506
G1 X251.754 Y226.754 E.00901
G1 X251.349 Y226.754 E.01512
G1 X247.84 Y223.246 E.18506
G1 X247.193 Y223.246 E.02414
G1 X250.702 Y226.754 E.18506
G1 X250.054 Y226.754 E.02414
G1 X246.546 Y223.246 E.18506
G1 X245.898 Y223.246 E.02414
G1 X249.407 Y226.754 E.18506
G1 X248.76 Y226.754 E.02414
G1 X245.251 Y223.246 E.18506
G1 X244.604 Y223.246 E.02414
G1 X248.113 Y226.754 E.18506
G1 X247.466 Y226.754 E.02414
G1 X243.957 Y223.246 E.18506
G1 X243.31 Y223.246 E.02414
G1 X246.818 Y226.754 E.18506
G1 X246.171 Y226.754 E.02414
G1 X242.662 Y223.246 E.18506
G1 X242.015 Y223.246 E.02414
G1 X245.524 Y226.754 E.18506
G1 X244.877 Y226.754 E.02414
G1 X241.368 Y223.246 E.18506
G1 X240.721 Y223.246 E.02414
G1 X244.23 Y226.754 E.18506
G1 X243.582 Y226.754 E.02414
G1 X240.073 Y223.246 E.18506
G1 X239.426 Y223.246 E.02414
G1 X242.935 Y226.754 E.18506
G1 X242.288 Y226.754 E.02414
G1 X238.779 Y223.246 E.18506
G1 X238.132 Y223.246 E.02414
G1 X241.641 Y226.754 E.18506
G1 X240.993 Y226.754 E.02414
G1 X237.485 Y223.246 E.18506
G1 X236.837 Y223.246 E.02414
G1 X240.346 Y226.754 E.18506
G1 X239.699 Y226.754 E.02414
G1 X236.19 Y223.246 E.18506
G1 X235.543 Y223.246 E.02414
G1 X239.052 Y226.754 E.18506
G1 X238.405 Y226.754 E.02414
G1 X234.896 Y223.246 E.18506
G1 X234.249 Y223.246 E.02414
G1 X237.757 Y226.754 E.18506
G1 X237.11 Y226.754 E.02414
G1 X233.601 Y223.246 E.18506
G1 X232.954 Y223.246 E.02414
G1 X236.463 Y226.754 E.18506
G1 X235.816 Y226.754 E.02414
G1 X232.307 Y223.246 E.18506
G1 X231.66 Y223.246 E.02414
G1 X235.169 Y226.754 E.18506
G1 X234.521 Y226.754 E.02414
G1 X231.012 Y223.246 E.18506
G1 X230.365 Y223.246 E.02414
G1 X233.874 Y226.754 E.18506
G1 X233.227 Y226.754 E.02414
G1 X229.718 Y223.246 E.18506
G1 X229.071 Y223.246 E.02414
G1 X232.58 Y226.754 E.18506
G1 X231.932 Y226.754 E.02414
G1 X228.424 Y223.246 E.18506
G1 X227.776 Y223.246 E.02414
G1 X231.285 Y226.754 E.18506
G1 X230.638 Y226.754 E.02414
G1 X227.129 Y223.246 E.18506
G1 X226.482 Y223.246 E.02414
G1 X229.991 Y226.754 E.18506
G1 X229.344 Y226.754 E.02414
G1 X225.835 Y223.246 E.18506
G1 X225.188 Y223.246 E.02414
G1 X228.696 Y226.754 E.18506
G1 X228.049 Y226.754 E.02414
G1 X224.54 Y223.246 E.18506
G1 X223.893 Y223.246 E.02414
G1 X227.402 Y226.754 E.18506
G1 X226.755 Y226.754 E.02414
G1 X223.246 Y223.246 E.18506
G1 X222.599 Y223.246 E.02414
G1 X226.108 Y226.754 E.18506
G1 X225.46 Y226.754 E.02414
G1 X221.951 Y223.246 E.18506
G1 X221.304 Y223.246 E.02414
G1 X224.813 Y226.754 E.18506
G1 X224.166 Y226.754 E.02414
G1 X220.657 Y223.246 E.18506
G1 X220.01 Y223.246 E.02414
G1 X223.519 Y226.754 E.18506
G1 X222.871 Y226.754 E.02414
G1 X219.363 Y223.246 E.18506
G1 X218.715 Y223.246 E.02414
G1 X222.224 Y226.754 E.18506
M73 P55 R9
G1 X221.577 Y226.754 E.02414
G1 X218.068 Y223.246 E.18506
G1 X217.421 Y223.246 E.02414
G1 X220.93 Y226.754 E.18506
G1 X220.283 Y226.754 E.02414
G1 X216.774 Y223.246 E.18506
G1 X216.127 Y223.246 E.02414
G1 X219.635 Y226.754 E.18506
G1 X218.988 Y226.754 E.02414
G1 X215.479 Y223.246 E.18506
G1 X214.832 Y223.246 E.02414
G1 X218.341 Y226.754 E.18506
G1 X217.694 Y226.754 E.02414
G1 X214.185 Y223.246 E.18506
G1 X213.538 Y223.246 E.02414
G1 X217.047 Y226.754 E.18506
G1 X216.399 Y226.754 E.02414
G1 X212.89 Y223.246 E.18506
G1 X212.243 Y223.246 E.02414
G1 X215.752 Y226.754 E.18506
G1 X215.105 Y226.754 E.02414
G1 X211.596 Y223.246 E.18506
G1 X210.949 Y223.246 E.02414
G1 X214.458 Y226.754 E.18506
G1 X213.81 Y226.754 E.02414
G1 X210.302 Y223.246 E.18506
G1 X209.654 Y223.246 E.02414
G1 X213.163 Y226.754 E.18506
G1 X212.516 Y226.754 E.02414
G1 X209.007 Y223.246 E.18506
G1 X208.36 Y223.246 E.02414
G1 X211.869 Y226.754 E.18506
G1 X211.222 Y226.754 E.02414
G1 X207.713 Y223.246 E.18506
G1 X207.066 Y223.246 E.02414
G1 X210.574 Y226.754 E.18506
G1 X209.927 Y226.754 E.02414
G1 X206.418 Y223.246 E.18506
G1 X205.771 Y223.246 E.02414
G1 X209.28 Y226.754 E.18506
G1 X208.633 Y226.754 E.02414
G1 X205.124 Y223.246 E.18506
G1 X204.477 Y223.246 E.02414
G1 X207.986 Y226.754 E.18506
G1 X207.338 Y226.754 E.02414
G1 X203.829 Y223.246 E.18506
G1 X203.182 Y223.246 E.02414
G1 X206.691 Y226.754 E.18506
G1 X206.044 Y226.754 E.02414
G1 X202.535 Y223.246 E.18506
G1 X201.888 Y223.246 E.02414
G1 X205.397 Y226.754 E.18506
G1 X204.749 Y226.754 E.02414
G1 X201.241 Y223.246 E.18506
G1 X200.593 Y223.246 E.02414
G1 X204.102 Y226.754 E.18506
G1 X203.455 Y226.754 E.02414
G1 X199.946 Y223.246 E.18506
G1 X199.299 Y223.246 E.02414
G1 X202.808 Y226.754 E.18506
G1 X202.161 Y226.754 E.02414
G1 X198.652 Y223.246 E.18506
G1 X198.005 Y223.246 E.02414
G1 X201.513 Y226.754 E.18506
G1 X200.866 Y226.754 E.02414
G1 X197.357 Y223.246 E.18506
G1 X196.71 Y223.246 E.02414
G1 X200.219 Y226.754 E.18506
G1 X199.572 Y226.754 E.02414
G1 X196.063 Y223.246 E.18506
G1 X195.416 Y223.246 E.02414
G1 X198.925 Y226.754 E.18506
G1 X198.277 Y226.754 E.02414
G1 X194.768 Y223.246 E.18506
G1 X194.121 Y223.246 E.02414
G1 X197.63 Y226.754 E.18506
G1 X196.983 Y226.754 E.02414
G1 X193.474 Y223.246 E.18506
G1 X192.827 Y223.246 E.02414
G1 X196.336 Y226.754 E.18506
G1 X195.688 Y226.754 E.02414
G1 X192.18 Y223.246 E.18506
G1 X191.532 Y223.246 E.02414
G1 X195.041 Y226.754 E.18506
G1 X194.394 Y226.754 E.02414
G1 X190.885 Y223.246 E.18506
G1 X190.238 Y223.246 E.02414
G1 X193.747 Y226.754 E.18506
G1 X193.1 Y226.754 E.02414
G1 X189.591 Y223.246 E.18506
G1 X188.944 Y223.246 E.02414
G1 X192.452 Y226.754 E.18506
G1 X191.805 Y226.754 E.02414
G1 X188.296 Y223.246 E.18506
G1 X187.649 Y223.246 E.02414
G1 X191.158 Y226.754 E.18506
G1 X190.511 Y226.754 E.02414
G1 X187.002 Y223.246 E.18506
G1 X186.355 Y223.246 E.02414
G1 X189.864 Y226.754 E.18506
G1 X189.216 Y226.754 E.02414
G1 X185.707 Y223.246 E.18506
G1 X185.06 Y223.246 E.02414
G1 X188.569 Y226.754 E.18506
G1 X187.922 Y226.754 E.02414
G1 X184.413 Y223.246 E.18506
G1 X183.766 Y223.246 E.02414
G1 X187.275 Y226.754 E.18506
G1 X186.627 Y226.754 E.02414
G1 X183.119 Y223.246 E.18506
G1 X182.471 Y223.246 E.02414
G1 X185.98 Y226.754 E.18506
G1 X185.333 Y226.754 E.02414
G1 X181.824 Y223.246 E.18506
G1 X181.177 Y223.246 E.02414
G1 X184.686 Y226.754 E.18506
G1 X184.039 Y226.754 E.02414
G1 X180.53 Y223.246 E.18506
G1 X179.883 Y223.246 E.02414
G1 X183.391 Y226.754 E.18506
G1 X182.744 Y226.754 E.02414
M73 P56 R9
G1 X179.235 Y223.246 E.18506
G1 X178.588 Y223.246 E.02414
G1 X182.097 Y226.754 E.18506
G1 X181.45 Y226.754 E.02414
G1 X177.941 Y223.246 E.18506
G1 X177.294 Y223.246 E.02414
G1 X180.803 Y226.754 E.18506
G1 X180.155 Y226.754 E.02414
G1 X176.646 Y223.246 E.18506
G1 X175.999 Y223.246 E.02414
G1 X179.508 Y226.754 E.18506
G1 X178.861 Y226.754 E.02414
G1 X175.352 Y223.246 E.18506
G1 X174.705 Y223.246 E.02414
G1 X178.214 Y226.754 E.18506
G1 X177.566 Y226.754 E.02414
G1 X174.058 Y223.246 E.18506
G1 X173.41 Y223.246 E.02414
G1 X176.919 Y226.754 E.18506
G1 X176.272 Y226.754 E.02414
G1 X172.763 Y223.246 E.18506
G1 X172.116 Y223.246 E.02414
G1 X175.625 Y226.754 E.18506
G1 X174.978 Y226.754 E.02414
G1 X171.469 Y223.246 E.18506
G1 X170.822 Y223.246 E.02414
G1 X174.33 Y226.754 E.18506
G1 X173.683 Y226.754 E.02414
G1 X170.174 Y223.246 E.18506
G1 X169.527 Y223.246 E.02414
G1 X173.036 Y226.754 E.18506
G1 X172.389 Y226.754 E.02414
G1 X168.88 Y223.246 E.18506
G1 X168.233 Y223.246 E.02414
G1 X171.741 Y226.754 E.18506
G1 X171.094 Y226.754 E.02414
G1 X167.585 Y223.246 E.18506
G1 X166.938 Y223.246 E.02414
G1 X170.447 Y226.754 E.18506
G1 X169.8 Y226.754 E.02414
G1 X166.291 Y223.246 E.18506
G1 X165.644 Y223.246 E.02414
G1 X169.153 Y226.754 E.18506
G1 X168.505 Y226.754 E.02414
G1 X164.997 Y223.246 E.18506
G1 X164.349 Y223.246 E.02414
G1 X167.858 Y226.754 E.18506
G1 X167.211 Y226.754 E.02414
G1 X163.702 Y223.246 E.18506
G1 X163.055 Y223.246 E.02414
G1 X166.564 Y226.754 E.18506
G1 X165.917 Y226.754 E.02414
G1 X162.408 Y223.246 E.18506
G1 X161.761 Y223.246 E.02414
G1 X165.269 Y226.754 E.18506
G1 X164.622 Y226.754 E.02414
G1 X161.113 Y223.246 E.18506
G1 X160.466 Y223.246 E.02414
G1 X163.975 Y226.754 E.18506
G1 X163.328 Y226.754 E.02414
G1 X159.819 Y223.246 E.18506
G1 X159.172 Y223.246 E.02414
G1 X162.68 Y226.754 E.18506
G1 X162.033 Y226.754 E.02414
G1 X158.524 Y223.246 E.18506
G1 X157.877 Y223.246 E.02414
G1 X161.386 Y226.754 E.18506
G1 X160.739 Y226.754 E.02414
G1 X157.23 Y223.246 E.18506
G1 X156.583 Y223.246 E.02414
G1 X160.092 Y226.754 E.18506
G1 X159.444 Y226.754 E.02414
G1 X155.936 Y223.246 E.18506
G1 X155.288 Y223.246 E.02414
G1 X158.797 Y226.754 E.18506
G1 X158.15 Y226.754 E.02414
G1 X154.641 Y223.246 E.18506
G1 X153.994 Y223.246 E.02414
G1 X157.503 Y226.754 E.18506
G1 X156.856 Y226.754 E.02414
G1 X153.347 Y223.246 E.18506
G1 X152.699 Y223.246 E.02414
G1 X156.208 Y226.754 E.18506
G1 X155.561 Y226.754 E.02414
G1 X152.052 Y223.246 E.18506
G1 X151.405 Y223.246 E.02414
G1 X154.914 Y226.754 E.18506
G1 X154.267 Y226.754 E.02414
G1 X150.758 Y223.246 E.18506
G1 X150.111 Y223.246 E.02414
G1 X153.619 Y226.754 E.18506
G1 X152.972 Y226.754 E.02414
G1 X149.463 Y223.246 E.18506
G1 X148.816 Y223.246 E.02414
G1 X152.325 Y226.754 E.18506
G1 X151.678 Y226.754 E.02414
G1 X148.169 Y223.246 E.18506
G1 X147.522 Y223.246 E.02414
G1 X151.031 Y226.754 E.18506
G1 X150.383 Y226.754 E.02414
G1 X146.875 Y223.246 E.18506
G1 X146.227 Y223.246 E.02414
G1 X149.736 Y226.754 E.18506
G1 X149.089 Y226.754 E.02414
G1 X145.58 Y223.246 E.18506
G1 X144.933 Y223.246 E.02414
G1 X148.442 Y226.754 E.18506
G1 X147.795 Y226.754 E.02414
G1 X144.286 Y223.246 E.18506
G1 X143.638 Y223.246 E.02414
G1 X147.147 Y226.754 E.18506
G1 X146.5 Y226.754 E.02414
G1 X142.991 Y223.246 E.18506
G1 X142.344 Y223.246 E.02414
G1 X145.853 Y226.754 E.18506
G1 X145.206 Y226.754 E.02414
G1 X141.697 Y223.246 E.18506
G1 X141.05 Y223.246 E.02414
G1 X144.558 Y226.754 E.18506
G1 X143.911 Y226.754 E.02414
G1 X140.402 Y223.246 E.18506
G1 X139.755 Y223.246 E.02414
M73 P57 R9
G1 X143.264 Y226.754 E.18506
G1 X142.617 Y226.754 E.02414
G1 X139.108 Y223.246 E.18506
G1 X138.461 Y223.246 E.02414
G1 X141.97 Y226.754 E.18506
G1 X141.322 Y226.754 E.02414
G1 X137.814 Y223.246 E.18506
G1 X137.166 Y223.246 E.02414
G1 X140.675 Y226.754 E.18506
G1 X140.028 Y226.754 E.02414
G1 X136.519 Y223.246 E.18506
G1 X135.872 Y223.246 E.02414
G1 X139.381 Y226.754 E.18506
G1 X138.734 Y226.754 E.02414
G1 X135.225 Y223.246 E.18506
G1 X134.577 Y223.246 E.02414
G1 X138.086 Y226.754 E.18506
G1 X137.439 Y226.754 E.02414
G1 X133.93 Y223.246 E.18506
G1 X133.283 Y223.246 E.02414
G1 X136.792 Y226.754 E.18506
G1 X136.145 Y226.754 E.02414
G1 X132.636 Y223.246 E.18506
G1 X131.989 Y223.246 E.02414
G1 X135.497 Y226.754 E.18506
G1 X134.85 Y226.754 E.02414
G1 X131.341 Y223.246 E.18506
G1 X130.694 Y223.246 E.02414
G1 X134.203 Y226.754 E.18506
G1 X133.556 Y226.754 E.02414
G1 X130.047 Y223.246 E.18506
G1 X129.4 Y223.246 E.02414
G1 X132.909 Y226.754 E.18506
G1 X132.261 Y226.754 E.02414
G1 X128.753 Y223.246 E.18506
G1 X128.105 Y223.246 E.02414
G1 X131.614 Y226.754 E.18506
G1 X130.967 Y226.754 E.02414
G1 X127.458 Y223.246 E.18506
G1 X126.811 Y223.246 E.02414
G1 X130.32 Y226.754 E.18506
G1 X129.673 Y226.754 E.02414
G1 X126.164 Y223.246 E.18506
G1 X125.516 Y223.246 E.02414
G1 X129.025 Y226.754 E.18506
G1 X128.378 Y226.754 E.02414
G1 X124.869 Y223.246 E.18506
G1 X124.222 Y223.246 E.02414
G1 X127.731 Y226.754 E.18506
G1 X127.084 Y226.754 E.02414
G1 X123.575 Y223.246 E.18506
G1 X122.928 Y223.246 E.02414
G1 X126.436 Y226.754 E.18506
G1 X125.789 Y226.754 E.02414
G1 X122.28 Y223.246 E.18506
G1 X121.633 Y223.246 E.02414
G1 X125.142 Y226.754 E.18506
G1 X124.495 Y226.754 E.02414
G1 X120.986 Y223.246 E.18506
G1 X120.339 Y223.246 E.02414
G1 X123.848 Y226.754 E.18506
G1 X123.2 Y226.754 E.02414
G1 X119.692 Y223.246 E.18506
G1 X119.044 Y223.246 E.02414
G1 X122.553 Y226.754 E.18506
G1 X121.906 Y226.754 E.02414
G1 X118.397 Y223.246 E.18506
G1 X117.75 Y223.246 E.02414
G1 X121.259 Y226.754 E.18506
G1 X120.612 Y226.754 E.02414
G1 X117.103 Y223.246 E.18506
G1 X116.455 Y223.246 E.02414
G1 X119.964 Y226.754 E.18506
G1 X119.317 Y226.754 E.02414
G1 X115.808 Y223.246 E.18506
G1 X115.161 Y223.246 E.02414
G1 X118.67 Y226.754 E.18506
G1 X118.023 Y226.754 E.02414
G1 X114.514 Y223.246 E.18506
G1 X113.867 Y223.246 E.02414
G1 X117.375 Y226.754 E.18506
G1 X116.728 Y226.754 E.02414
G1 X113.219 Y223.246 E.18506
G1 X112.572 Y223.246 E.02414
G1 X116.081 Y226.754 E.18506
G1 X115.434 Y226.754 E.02414
G1 X111.925 Y223.246 E.18506
G1 X111.278 Y223.246 E.02414
G1 X114.787 Y226.754 E.18506
G1 X114.139 Y226.754 E.02414
G1 X110.631 Y223.246 E.18506
G1 X109.983 Y223.246 E.02414
G1 X113.492 Y226.754 E.18506
G1 X112.845 Y226.754 E.02414
G1 X109.336 Y223.246 E.18506
G1 X108.689 Y223.246 E.02414
G1 X112.198 Y226.754 E.18506
G1 X111.551 Y226.754 E.02414
G1 X108.042 Y223.246 E.18506
G1 X107.394 Y223.246 E.02414
G1 X110.903 Y226.754 E.18506
G1 X110.256 Y226.754 E.02414
G1 X106.747 Y223.246 E.18506
G1 X106.1 Y223.246 E.02414
G1 X109.609 Y226.754 E.18506
G1 X108.962 Y226.754 E.02414
G1 X105.453 Y223.246 E.18506
G1 X104.806 Y223.246 E.02414
G1 X108.314 Y226.754 E.18506
G1 X107.667 Y226.754 E.02414
G1 X104.158 Y223.246 E.18506
G1 X103.511 Y223.246 E.02414
G1 X107.02 Y226.754 E.18506
G1 X106.373 Y226.754 E.02414
G1 X102.864 Y223.246 E.18506
G1 X102.217 Y223.246 E.02414
G1 X105.726 Y226.754 E.18506
G1 X105.078 Y226.754 E.02414
G1 X101.57 Y223.246 E.18506
G1 X100.922 Y223.246 E.02414
G1 X104.431 Y226.754 E.18506
G1 X103.784 Y226.754 E.02414
M73 P58 R9
G1 X100.275 Y223.246 E.18506
G1 X99.628 Y223.246 E.02414
G1 X103.137 Y226.754 E.18506
G1 X102.49 Y226.754 E.02414
G1 X98.981 Y223.246 E.18506
G1 X98.333 Y223.246 E.02414
G1 X101.842 Y226.754 E.18506
G1 X101.195 Y226.754 E.02414
G1 X97.686 Y223.246 E.18506
G1 X97.039 Y223.246 E.02414
G1 X100.548 Y226.754 E.18506
G1 X99.901 Y226.754 E.02414
G1 X96.392 Y223.246 E.18506
G1 X95.745 Y223.246 E.02414
G1 X99.253 Y226.754 E.18506
G1 X98.606 Y226.754 E.02414
G1 X95.097 Y223.246 E.18506
G1 X94.45 Y223.246 E.02414
G1 X97.959 Y226.754 E.18506
G1 X97.312 Y226.754 E.02414
G1 X93.803 Y223.246 E.18506
G1 X93.156 Y223.246 E.02414
G1 X96.665 Y226.754 E.18506
G1 X96.017 Y226.754 E.02414
G1 X92.509 Y223.246 E.18506
G1 X91.861 Y223.246 E.02414
G1 X95.37 Y226.754 E.18506
G1 X94.723 Y226.754 E.02414
G1 X91.214 Y223.246 E.18506
G1 X90.567 Y223.246 E.02414
G1 X94.076 Y226.754 E.18506
G1 X93.428 Y226.754 E.02414
G1 X89.92 Y223.246 E.18506
G1 X89.272 Y223.246 E.02414
G1 X92.781 Y226.754 E.18506
G1 X92.134 Y226.754 E.02414
M73 P58 R8
G1 X88.625 Y223.246 E.18506
G1 X87.978 Y223.246 E.02414
G1 X91.487 Y226.754 E.18506
G1 X90.84 Y226.754 E.02414
G1 X87.331 Y223.246 E.18506
G1 X86.684 Y223.246 E.02414
G1 X90.192 Y226.754 E.18506
G1 X89.545 Y226.754 E.02414
G1 X86.036 Y223.246 E.18506
G1 X85.389 Y223.246 E.02414
G1 X88.898 Y226.754 E.18506
G1 X88.251 Y226.754 E.02414
G1 X84.742 Y223.246 E.18506
G1 X84.095 Y223.246 E.02414
G1 X87.604 Y226.754 E.18506
G1 X86.956 Y226.754 E.02414
G1 X83.448 Y223.246 E.18506
G1 X82.8 Y223.246 E.02414
G1 X86.309 Y226.754 E.18506
G1 X85.662 Y226.754 E.02414
G1 X82.153 Y223.246 E.18506
G1 X81.506 Y223.246 E.02414
G1 X85.015 Y226.754 E.18506
G1 X84.367 Y226.754 E.02414
G1 X80.859 Y223.246 E.18506
G1 X80.211 Y223.246 E.02414
G1 X83.72 Y226.754 E.18506
G1 X83.073 Y226.754 E.02414
G1 X79.564 Y223.246 E.18506
G1 X78.917 Y223.246 E.02414
G1 X82.426 Y226.754 E.18506
G1 X81.779 Y226.754 E.02414
G1 X78.27 Y223.246 E.18506
G1 X77.623 Y223.246 E.02414
G1 X81.131 Y226.754 E.18506
G1 X80.484 Y226.754 E.02414
G1 X76.975 Y223.246 E.18506
G1 X76.328 Y223.246 E.02414
G1 X79.837 Y226.754 E.18506
G1 X79.19 Y226.754 E.02414
G1 X75.681 Y223.246 E.18506
G1 X75.034 Y223.246 E.02414
G1 X78.543 Y226.754 E.18506
G1 X77.895 Y226.754 E.02414
G1 X74.387 Y223.246 E.18506
G1 X73.739 Y223.246 E.02414
G1 X77.248 Y226.754 E.18506
G1 X76.601 Y226.754 E.02414
G1 X73.092 Y223.246 E.18506
G1 X72.445 Y223.246 E.02414
G1 X75.954 Y226.754 E.18506
G1 X75.306 Y226.754 E.02414
G1 X71.798 Y223.246 E.18506
G1 X71.15 Y223.246 E.02414
G1 X74.659 Y226.754 E.18506
G1 X74.012 Y226.754 E.02414
G1 X70.503 Y223.246 E.18506
G1 X69.856 Y223.246 E.02414
G1 X73.365 Y226.754 E.18506
G1 X72.718 Y226.754 E.02414
G1 X69.209 Y223.246 E.18506
G1 X68.562 Y223.246 E.02414
G1 X72.07 Y226.754 E.18506
G1 X71.423 Y226.754 E.02414
G1 X67.914 Y223.246 E.18506
G1 X67.267 Y223.246 E.02414
G1 X70.776 Y226.754 E.18506
G1 X70.129 Y226.754 E.02414
G1 X66.62 Y223.246 E.18506
G1 X65.973 Y223.246 E.02414
G1 X69.482 Y226.754 E.18506
G1 X68.834 Y226.754 E.02414
G1 X65.325 Y223.246 E.18506
G1 X64.678 Y223.246 E.02414
G1 X68.187 Y226.754 E.18506
G1 X67.54 Y226.754 E.02414
G1 X64.031 Y223.246 E.18506
G1 X63.384 Y223.246 E.02414
G1 X66.893 Y226.754 E.18506
G1 X66.245 Y226.754 E.02414
G1 X62.737 Y223.246 E.18506
G1 X62.089 Y223.246 E.02414
G1 X65.598 Y226.754 E.18506
G1 X64.951 Y226.754 E.02414
G1 X61.442 Y223.246 E.18506
M73 P59 R8
G1 X60.795 Y223.246 E.02414
G1 X64.304 Y226.754 E.18506
G1 X63.657 Y226.754 E.02414
G1 X60.148 Y223.246 E.18506
G1 X59.501 Y223.246 E.02414
G1 X63.009 Y226.754 E.18506
G1 X62.362 Y226.754 E.02414
G1 X58.853 Y223.246 E.18506
G1 X58.206 Y223.246 E.02414
G1 X61.715 Y226.754 E.18506
G1 X61.068 Y226.754 E.02414
G1 X57.559 Y223.246 E.18506
G1 X56.912 Y223.246 E.02414
G1 X60.421 Y226.754 E.18506
G1 X59.773 Y226.754 E.02414
G1 X56.264 Y223.246 E.18506
G1 X55.617 Y223.246 E.02414
G1 X59.126 Y226.754 E.18506
G1 X58.479 Y226.754 E.02414
G1 X54.97 Y223.246 E.18506
G1 X54.323 Y223.246 E.02414
G1 X57.832 Y226.754 E.18506
G1 X57.184 Y226.754 E.02414
G1 X53.676 Y223.246 E.18506
G1 X53.028 Y223.246 E.02414
G1 X56.537 Y226.754 E.18506
G1 X55.89 Y226.754 E.02414
G1 X52.381 Y223.246 E.18506
G1 X51.734 Y223.246 E.02414
G1 X55.243 Y226.754 E.18506
G1 X54.596 Y226.754 E.02414
G1 X51.087 Y223.246 E.18506
G1 X50.44 Y223.246 E.02414
G1 X53.948 Y226.754 E.18506
G1 X53.301 Y226.754 E.02414
G1 X49.792 Y223.246 E.18506
G1 X49.145 Y223.246 E.02414
G1 X52.654 Y226.754 E.18506
G1 X52.007 Y226.754 E.02414
G1 X48.498 Y223.246 E.18506
G1 X47.851 Y223.246 E.02414
G1 X51.36 Y226.754 E.18506
G1 X50.712 Y226.754 E.02414
G1 X47.203 Y223.246 E.18506
G1 X46.556 Y223.246 E.02414
G1 X50.065 Y226.754 E.18506
G1 X49.418 Y226.754 E.02414
G1 X45.909 Y223.246 E.18506
G1 X45.262 Y223.246 E.02414
G1 X48.771 Y226.754 E.18506
G1 X48.123 Y226.754 E.02414
G1 X44.615 Y223.246 E.18506
G1 X43.967 Y223.246 E.02414
G1 X47.476 Y226.754 E.18506
G1 X46.829 Y226.754 E.02414
G1 X43.32 Y223.246 E.18506
G1 X42.673 Y223.246 E.02414
G1 X46.182 Y226.754 E.18506
G1 X45.535 Y226.754 E.02414
G1 X42.026 Y223.246 E.18506
G1 X41.379 Y223.246 E.02414
G1 X44.887 Y226.754 E.18506
G1 X44.24 Y226.754 E.02414
G1 X40.731 Y223.246 E.18506
G1 X40.084 Y223.246 E.02414
G1 X43.593 Y226.754 E.18506
G1 X42.946 Y226.754 E.02414
G1 X39.437 Y223.246 E.18506
G1 X38.79 Y223.246 E.02414
G1 X42.299 Y226.754 E.18506
G1 X41.651 Y226.754 E.02414
G1 X38.142 Y223.246 E.18506
G1 X37.495 Y223.246 E.02414
G1 X41.004 Y226.754 E.18506
G1 X40.357 Y226.754 E.02414
G1 X36.848 Y223.246 E.18506
G1 X36.201 Y223.246 E.02414
G1 X39.71 Y226.754 E.18506
G1 X39.062 Y226.754 E.02414
G1 X35.554 Y223.246 E.18506
G1 X34.906 Y223.246 E.02414
G1 X38.415 Y226.754 E.18506
G1 X37.768 Y226.754 E.02414
G1 X34.259 Y223.246 E.18506
G1 X33.612 Y223.246 E.02414
G1 X37.121 Y226.754 E.18506
G1 X36.474 Y226.754 E.02414
G1 X32.965 Y223.246 E.18506
G1 X32.318 Y223.246 E.02414
G1 X35.826 Y226.754 E.18506
G1 X35.179 Y226.754 E.02414
G1 X31.67 Y223.246 E.18506
G1 X31.023 Y223.246 E.02414
G1 X34.532 Y226.754 E.18506
G1 X33.885 Y226.754 E.02414
G1 X30.376 Y223.246 E.18506
G1 X29.729 Y223.246 E.02414
G1 X33.238 Y226.754 E.18506
G1 X32.59 Y226.754 E.02414
G1 X29.081 Y223.246 E.18506
G1 X28.434 Y223.246 E.02414
G1 X31.943 Y226.754 E.18506
G1 X31.296 Y226.754 E.02414
G1 X27.787 Y223.246 E.18506
G1 X27.14 Y223.246 E.02414
G1 X30.649 Y226.754 E.18506
G1 X30.001 Y226.754 E.02414
G1 X26.493 Y223.246 E.18506
G1 X25.845 Y223.246 E.02414
G1 X29.354 Y226.754 E.18506
G1 X28.707 Y226.754 E.02414
G1 X25.198 Y223.246 E.18506
G1 X24.551 Y223.246 E.02414
G1 X28.06 Y226.754 E.18506
G1 X27.413 Y226.754 E.02414
G1 X23.904 Y223.246 E.18506
G1 X23.257 Y223.246 E.02414
G1 X26.765 Y226.754 E.18506
G1 X26.118 Y226.754 E.02414
G1 X22.609 Y223.246 E.18506
G1 X21.962 Y223.246 E.02414
G1 X25.471 Y226.754 E.18506
M73 P60 R8
G1 X24.824 Y226.754 E.02414
G1 X21.315 Y223.246 E.18506
G1 X20.668 Y223.246 E.02414
G1 X24.177 Y226.754 E.18506
G1 X23.529 Y226.754 E.02414
G1 X20.02 Y223.246 E.18506
G1 X19.373 Y223.246 E.02414
G1 X22.882 Y226.754 E.18506
G1 X22.235 Y226.754 E.02414
G1 X18.726 Y223.246 E.18506
G1 X18.079 Y223.246 E.02414
G1 X21.588 Y226.754 E.18506
G1 X20.94 Y226.754 E.02414
G1 X17.432 Y223.246 E.18506
G1 X16.784 Y223.246 E.02414
G1 X20.293 Y226.754 E.18506
G1 X19.646 Y226.754 E.02414
G1 X16.137 Y223.246 E.18506
G1 X15.49 Y223.246 E.02414
G1 X18.999 Y226.754 E.18506
G1 X18.352 Y226.754 E.02414
G1 X14.843 Y223.246 E.18506
G1 X14.196 Y223.246 E.02414
G1 X17.704 Y226.754 E.18506
G1 X17.057 Y226.754 E.02414
G1 X13.548 Y223.246 E.18506
G1 X12.901 Y223.246 E.02414
G1 X16.41 Y226.754 E.18506
G1 X15.763 Y226.754 E.02414
G1 X12.254 Y223.246 E.18506
G1 X11.607 Y223.246 E.02414
G1 X15.115 Y226.754 E.18506
G1 X14.468 Y226.754 E.02414
G1 X10.959 Y223.246 E.18506
G1 X10.312 Y223.246 E.02414
G1 X13.821 Y226.754 E.18506
G1 X13.174 Y226.754 E.02414
G1 X9.665 Y223.246 E.18506
G1 X9.018 Y223.246 E.02414
G1 X12.527 Y226.754 E.18506
G1 X11.879 Y226.754 E.02414
G1 X8.371 Y223.246 E.18506
G1 X7.754 Y223.246 E.02298
G1 X7.754 Y222.629 E.02298
G1 X4.246 Y219.121 E.18506
G1 X4.246 Y219.768 E.02414
G1 X11.232 Y226.754 E.36847
G1 X10.585 Y226.754 E.02414
G1 X4.246 Y220.415 E.33434
G1 X4.246 Y221.062 E.02414
G1 X9.938 Y226.754 E.30021
G1 X9.291 Y226.754 E.02414
G1 X4.246 Y221.709 E.26607
G1 X4.246 Y222.357 E.02414
G1 X8.643 Y226.754 E.23194
G1 X7.996 Y226.754 E.02414
G1 X4.246 Y223.004 E.1978
G1 X4.246 Y223.651 E.02414
G1 X7.349 Y226.754 E.16367
G1 X6.702 Y226.754 E.02414
G1 X4.246 Y224.298 E.12954
G1 X4.246 Y224.945 E.02414
G1 X6.054 Y226.754 E.0954
G1 X5.407 Y226.754 E.02414
G1 X4.246 Y225.593 E.06127
G1 X4.246 Y226.24 E.02414
G1 X4.966 Y226.96 E.03798
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; LAYER_HEIGHT: 0.2
; WIPE_START
G1 F6300
G1 X4.246 Y226.24 E-.38702
G1 X4.246 Y225.593 E-.24594
G1 X4.482 Y225.829 E-.12704
; WIPE_END
G1 E-.04 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====





    ;updata chamber autocooling in Xth layer
    
        
            M142 P1 R30 S40 U0 V1.0 O45; set PLA/TPU ND0.4 chamber autocooling
        
    

    M622.1 S0
    M1002 judge_flag ventobox_replace_aux1_fan_flag
    M622 J0
    M106 P10 S0; set left aux fan
    M623
;not reset fan


; update layer progress
M73 L2
M991 S0 P1 ;notify layer change


M106 S255
; open powerlost recovery
M1003 S1
; OBJECT_ID: 15
M204 S10000
G17
G3 Z.6 I.754 J.955 P1  F36000
G1 X247.602 Y33.79 Z.6
G1 Z.4
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X247.602 Y33.398 E.01301
G1 X8.398 Y33.398 E7.93484
G1 X8.398 Y222.602 E6.27625
G1 X247.602 Y222.602 E7.93484
G1 X247.602 Y33.85 E6.26125
M204 S250
G1 X247.21 Y33.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X8.79 Y33.79 E7.32598
G1 X8.79 Y222.21 E5.78962
G1 X247.21 Y222.21 E7.32598
M73 P61 R8
G1 X247.21 Y33.85 E5.78778
; WIPE_START
M204 S10000
G1 X245.21 Y33.849 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X245.493 Y41.477 Z.8 F36000
G1 X252.398 Y227.398 Z.8
G1 Z.4
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X252.398 Y28.602 E6.59442
G1 X3.602 Y28.602 E8.25302
G1 X3.602 Y227.398 E6.59442
G1 X252.338 Y227.398 E8.25103
M204 S250
G1 X252.79 Y227.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X252.79 Y28.21 E6.13254
G1 X3.21 Y28.21 E7.6689
G1 X3.21 Y227.79 E6.13254
G1 X252.73 Y227.79 E7.66705
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

; WIPE_START
M204 S10000
G1 X252.731 Y225.79 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X249.127 Y31.222 F36000
G1 Z.8
M73 P62 R8
G1 Z.4
G1 E.8 F1800
; FEATURE: Internal solid infill
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.514 Y31.486 E.01178
G1 X249.778 Y31.873 E.01178
G1 X249.778 Y31.222 E.01636
G1 X249.187 Y31.222 E.01485
G1 X250.498 Y31.376 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X250.498 Y30.502 E.02686
G1 X5.502 Y30.502 E7.52783
G1 X5.502 Y225.498 E5.9915
G1 X250.498 Y225.498 E7.52783
G1 X250.498 Y31.436 E5.9628
G1 X250.875 Y31.376 F36000
G1 F11934.123
G1 X250.875 Y30.125 E.03844
G1 X5.125 Y30.125 E7.551
G1 X5.125 Y225.875 E6.01468
G1 X250.875 Y225.875 E7.551
G1 X250.875 Y31.436 E5.97439
G1 X251.252 Y31.376 F36000
G1 F11934.123
G1 X251.252 Y29.748 E.05003
G1 X4.748 Y29.748 E7.57417
G1 X4.748 Y226.252 E6.03785
G1 X251.252 Y226.252 E7.57417
G1 X251.252 Y31.436 E5.98598
G1 X251.629 Y31.376 F36000
G1 F11934.123
M73 P62 R7
G1 X251.629 Y29.371 E.06162
M73 P63 R7
G1 X4.371 Y29.371 E7.59734
G1 X4.371 Y226.629 E6.06102
G1 X251.629 Y226.629 E7.59734
G1 X251.629 Y31.436 E5.99756
G1 X252.006 Y31.376 F36000
G1 F11934.123
G1 X252.006 Y28.994 E.0732
G1 X3.994 Y28.994 E7.62052
G1 X3.994 Y227.006 E6.08419
G1 X252.006 Y227.006 E7.62052
G1 X252.006 Y31.436 E6.00915
G1 X249.127 Y224.778 F36000
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.778 Y224.778 E.01636
G1 X249.778 Y224.127 E.01636
G1 X249.514 Y224.514 E.01178
G1 X249.177 Y224.744 E.01027
G1 X247.806 Y225.155 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.26 Y225.138 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.514
G3 X250.121 Y225.121 I1.157 J24.86 E.05682
G1 X250.121 Y223.715 E.04293
; LINE_WIDTH: 0.40714
G1 F12355.17
G1 X250.133 Y223.451 E.00783
; LINE_WIDTH: 0.352028
G1 F14558.041
G2 X250.155 Y222.806 I-11.946 J-.715 E.01627
G1 X250.155 Y33.194 E4.77599
; LINE_WIDTH: 0.368975
G1 F13801.353
G1 X250.138 Y32.74 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.526
G3 X250.121 Y30.879 I49.729 J-1.385 E.05681
G1 X248.715 Y30.879 E.04293
; LINE_WIDTH: 0.402988
M73 P64 R7
G1 F12497.657
G1 X248.26 Y30.862 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X247.806 Y30.845 E.01145
G1 X8.194 Y30.845 E6.03511
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.74 Y30.862 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y30.879 I-1.158 J-24.87 E.05682
G1 X5.879 Y32.285 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X5.862 Y32.74 E.01334
; LINE_WIDTH: 0.352021
G1 F14558.364
G1 X5.845 Y33.194 E.01146
G1 X5.845 Y222.806 E4.77589
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X5.862 Y223.26 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y225.121 I-24.87 J1.158 E.05682
G1 X7.285 Y225.121 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X7.74 Y225.138 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X8.194 Y225.155 E.01145
G1 X247.746 Y225.155 E6.0336
G1 X6.873 Y224.778 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.486 Y224.514 E.01178
G1 X6.222 Y224.127 E.01178
G1 X6.222 Y224.778 E.01636
G1 X6.813 Y224.778 E.01485
G1 X8.194 Y224.845 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.783 Y224.777 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X7.371 Y224.709 E.0127
G1 X6.728 Y224.272 E.02365
G1 X6.291 Y223.629 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X6.234 Y223.394 E.00717
; LINE_WIDTH: 0.352033
G1 F14557.786
G3 X6.155 Y222.806 I1.627 J-.52 E.01504
G1 X6.155 Y33.194 E4.77608
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X6.223 Y32.783 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X6.291 Y32.371 E.0127
G1 X6.728 Y31.728 E.02365
G1 X7.371 Y31.291 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X7.606 Y31.234 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X8.194 Y31.155 I.52 J1.627 E.01504
G1 X247.806 Y31.155 E6.0353
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.217 Y31.223 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X248.629 Y31.291 E.0127
G1 X249.272 Y31.728 E.02365
G1 X249.709 Y32.371 E.02365
; LINE_WIDTH: 0.402985
G1 F12497.745
G1 X249.777 Y32.783 E.01225
; LINE_WIDTH: 0.352023
G1 F14558.265
G1 X249.845 Y33.194 E.01052
G1 X249.845 Y222.806 E4.77592
G1 X249.823 Y223.159 E.00893
; LINE_WIDTH: 0.38144
G1 F13293.16
G1 X249.766 Y223.394 E.00667
; LINE_WIDTH: 0.418261
G1 F11989.116
G1 X249.709 Y223.629 E.00739
G1 X249.272 Y224.272 E.02377
G1 X248.629 Y224.709 E.02377
; LINE_WIDTH: 0.407145
G1 F12355
G1 X248.394 Y224.766 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X247.806 Y224.845 I-.52 J-1.627 E.01504
G1 X8.254 Y224.845 E6.03379
G1 X8.194 Y224.502 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X7.52 Y224.363 E.02115
G1 X6.995 Y224.005 E.01954
G1 X6.637 Y223.48 E.01954
G3 X6.498 Y222.806 I1.557 J-.674 E.02129
G1 X6.498 Y33.194 E5.82608
G1 X6.637 Y32.52 E.02115
G1 X6.995 Y31.995 E.01954
G1 X7.52 Y31.637 E.01954
G3 X8.194 Y31.498 I.674 J1.557 E.02129
G1 X247.806 Y31.498 E7.3624
G1 X248.48 Y31.637 E.02115
G1 X249.005 Y31.995 E.01954
G1 X249.363 Y32.52 E.01954
G1 X249.502 Y33.194 E.02115
G1 X249.502 Y222.806 E5.82608
G3 X249.363 Y223.48 I-1.696 J0 E.02129
G1 X249.005 Y224.005 E.01954
G1 X248.48 Y224.363 E.01954
G3 X247.806 Y224.502 I-.674 J-1.557 E.02129
G1 X8.254 Y224.502 E7.36055
G1 X8.194 Y224.125 F36000
G1 F11934.123
G1 X7.67 Y224.017 E.01645
G1 X7.261 Y223.739 E.0152
G1 X6.983 Y223.33 E.0152
G3 X6.875 Y222.806 I1.211 J-.524 E.01656
G1 X6.875 Y33.194 E5.82608
G1 X6.983 Y32.67 E.01645
G1 X7.261 Y32.261 E.0152
G1 X7.67 Y31.983 E.0152
G3 X8.194 Y31.875 I.524 J1.211 E.01656
G1 X247.806 Y31.875 E7.3624
M73 P65 R7
G1 X248.33 Y31.983 E.01645
G1 X248.739 Y32.261 E.0152
G1 X249.017 Y32.67 E.0152
G1 X249.125 Y33.194 E.01645
G1 X249.125 Y222.806 E5.82608
G3 X249.017 Y223.33 I-1.32 J0 E.01656
G1 X248.739 Y223.739 E.0152
G1 X248.33 Y224.017 E.0152
G3 X247.806 Y224.125 I-.524 J-1.211 E.01656
G1 X8.254 Y224.125 E7.36055
G1 X8.194 Y223.748 F36000
G1 F11934.123
G1 X7.82 Y223.671 E.01175
G1 X7.528 Y223.472 E.01085
G1 X7.329 Y223.18 E.01085
G1 X7.252 Y222.806 E.01175
G1 X7.252 Y33.194 E5.82608
G1 X7.329 Y32.82 E.01175
G1 X7.528 Y32.528 E.01085
G1 X7.82 Y32.329 E.01085
G1 X8.194 Y32.252 E.01175
G1 X247.806 Y32.252 E7.3624
G1 X248.18 Y32.329 E.01175
G1 X248.472 Y32.528 E.01085
G1 X248.671 Y32.82 E.01085
G1 X248.748 Y33.194 E.01175
G1 X248.748 Y222.806 E5.82608
G1 X248.671 Y223.18 E.01175
G1 X248.472 Y223.472 E.01085
G1 X248.18 Y223.671 E.01085
G1 X247.806 Y223.748 E.01175
G1 X8.254 Y223.748 E7.36055
G1 X8.194 Y223.371 F36000
G1 F11934.123
G3 X7.794 Y223.206 I0 J-.566 E.01365
G1 X7.637 Y222.903 E.01047
G1 X7.629 Y222.806 E.00301
G1 X7.629 Y33.194 E5.82608
G3 X7.794 Y32.794 I.566 J0 E.01365
G1 X8.097 Y32.637 E.01047
G1 X8.194 Y32.629 E.00301
G1 X247.806 Y32.629 E7.3624
G3 X248.371 Y33.194 I0 J.566 E.0273
G1 X248.371 Y222.806 E5.82608
G3 X248.206 Y223.206 I-.566 J0 E.01365
G1 X247.903 Y223.363 E.01047
G1 X247.806 Y223.371 E.00301
G1 X8.254 Y223.371 E7.36055
G1 X8.194 Y222.994 F36000
G1 F11934.123
G1 X8.061 Y222.939 E.00443
G1 X8.006 Y222.806 E.00443
G1 X8.006 Y33.194 E5.82608
G1 X8.061 Y33.061 E.00443
G1 X8.194 Y33.006 E.00443
G1 X247.806 Y33.006 E7.3624
G1 X247.939 Y33.061 E.00443
G1 X247.994 Y33.194 E.00443
M73 P66 R7
G1 X247.994 Y222.806 E5.82608
G1 X247.939 Y222.939 E.00443
G1 X247.806 Y222.994 E.00443
G1 X8.254 Y222.994 E7.36055
G1 X6.873 Y31.222 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.222 Y31.222 E.01636
G1 X6.222 Y31.873 E.01636
G1 X6.486 Y31.486 E.01178
G1 X6.823 Y31.256 E.01027
; CHANGE_LAYER
; Z_HEIGHT: 0.6
; LAYER_HEIGHT: 0.2
; WIPE_START
G1 F14588.129
G1 X6.486 Y31.486 E-.15521
G1 X6.222 Y31.873 E-.17801
G1 X6.222 Y31.222 E-.24729
G1 X6.695 Y31.222 E-.17949
; WIPE_END
G1 E-.04 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====





; update layer progress
M73 L3
M991 S0 P2 ;notify layer change


; OBJECT_ID: 15
G17
G3 Z.8 I-.013 J1.217 P1  F36000
G1 X247.602 Y33.79 Z.8
G1 Z.6
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X247.602 Y33.398 E.01301
G1 X8.398 Y33.398 E7.93484
G1 X8.398 Y222.602 E6.27625
G1 X247.602 Y222.602 E7.93484
G1 X247.602 Y33.85 E6.26125
M204 S250
G1 X247.21 Y33.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X8.79 Y33.79 E7.32598
G1 X8.79 Y222.21 E5.78962
G1 X247.21 Y222.21 E7.32598
G1 X247.21 Y33.85 E5.78778
; WIPE_START
M204 S10000
G1 X245.21 Y33.849 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X245.493 Y41.477 Z1 F36000
G1 X252.398 Y227.398 Z1
M73 P67 R7
G1 Z.6
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X252.398 Y28.602 E6.59442
G1 X3.602 Y28.602 E8.25302
G1 X3.602 Y227.398 E6.59442
G1 X252.338 Y227.398 E8.25103
M204 S250
G1 X252.79 Y227.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X252.79 Y28.21 E6.13254
G1 X3.21 Y28.21 E7.6689
G1 X3.21 Y227.79 E6.13254
G1 X252.73 Y227.79 E7.66705
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

; WIPE_START
M204 S10000
G1 X252.731 Y225.79 E-.76
; WIPE_END
G1 E-.04 F1800
M73 P67 R6
G1 X249.127 Y31.222 F36000
G1 Z1
G1 Z.6
G1 E.8 F1800
; FEATURE: Internal solid infill
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.514 Y31.486 E.01178
G1 X249.778 Y31.873 E.01178
G1 X249.778 Y31.222 E.01636
G1 X249.187 Y31.222 E.01485
G1 X250.498 Y31.376 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X250.498 Y30.502 E.02686
G1 X5.502 Y30.502 E7.52783
G1 X5.502 Y225.498 E5.9915
G1 X250.498 Y225.498 E7.52783
G1 X250.498 Y31.436 E5.9628
G1 X250.875 Y31.376 F36000
G1 F11934.123
M73 P68 R6
G1 X250.875 Y30.125 E.03844
G1 X5.125 Y30.125 E7.551
G1 X5.125 Y225.875 E6.01468
G1 X250.875 Y225.875 E7.551
G1 X250.875 Y31.436 E5.97439
G1 X251.252 Y31.376 F36000
G1 F11934.123
G1 X251.252 Y29.748 E.05003
G1 X4.748 Y29.748 E7.57417
G1 X4.748 Y226.252 E6.03785
G1 X251.252 Y226.252 E7.57417
G1 X251.252 Y31.436 E5.98598
G1 X251.629 Y31.376 F36000
G1 F11934.123
G1 X251.629 Y29.371 E.06162
G1 X4.371 Y29.371 E7.59734
G1 X4.371 Y226.629 E6.06102
M73 P69 R6
G1 X251.629 Y226.629 E7.59734
G1 X251.629 Y31.436 E5.99756
G1 X252.006 Y31.376 F36000
G1 F11934.123
G1 X252.006 Y28.994 E.0732
G1 X3.994 Y28.994 E7.62052
G1 X3.994 Y227.006 E6.08419
G1 X252.006 Y227.006 E7.62052
G1 X252.006 Y31.436 E6.00915
G1 X249.127 Y224.778 F36000
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.778 Y224.778 E.01636
G1 X249.778 Y224.127 E.01636
G1 X249.514 Y224.514 E.01178
G1 X249.177 Y224.744 E.01027
G1 X247.806 Y225.155 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.26 Y225.138 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.514
G3 X250.121 Y225.121 I1.157 J24.86 E.05682
G1 X250.121 Y223.715 E.04293
; LINE_WIDTH: 0.40714
G1 F12355.17
G1 X250.133 Y223.451 E.00783
; LINE_WIDTH: 0.352028
G1 F14558.041
G2 X250.155 Y222.806 I-11.946 J-.715 E.01627
G1 X250.155 Y33.194 E4.77599
; LINE_WIDTH: 0.368975
G1 F13801.353
G1 X250.138 Y32.74 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.526
G3 X250.121 Y30.879 I49.729 J-1.385 E.05681
G1 X248.715 Y30.879 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X248.26 Y30.862 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X247.806 Y30.845 E.01145
G1 X8.194 Y30.845 E6.03511
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.74 Y30.862 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y30.879 I-1.158 J-24.87 E.05682
G1 X5.879 Y32.285 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X5.862 Y32.74 E.01334
; LINE_WIDTH: 0.352021
G1 F14558.364
G1 X5.845 Y33.194 E.01146
G1 X5.845 Y222.806 E4.77589
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X5.862 Y223.26 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y225.121 I-24.87 J1.158 E.05682
G1 X7.285 Y225.121 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X7.74 Y225.138 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X8.194 Y225.155 E.01145
G1 X247.746 Y225.155 E6.0336
G1 X6.873 Y224.778 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.486 Y224.514 E.01178
G1 X6.222 Y224.127 E.01178
G1 X6.222 Y224.778 E.01636
M73 P70 R6
G1 X6.813 Y224.778 E.01485
G1 X8.194 Y224.845 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.783 Y224.777 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X7.371 Y224.709 E.0127
G1 X6.728 Y224.272 E.02365
G1 X6.291 Y223.629 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X6.234 Y223.394 E.00717
; LINE_WIDTH: 0.352033
G1 F14557.786
G3 X6.155 Y222.806 I1.627 J-.52 E.01504
G1 X6.155 Y33.194 E4.77608
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X6.223 Y32.783 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X6.291 Y32.371 E.0127
G1 X6.728 Y31.728 E.02365
G1 X7.371 Y31.291 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X7.606 Y31.234 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X8.194 Y31.155 I.52 J1.627 E.01504
G1 X247.806 Y31.155 E6.0353
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.217 Y31.223 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X248.629 Y31.291 E.0127
G1 X249.272 Y31.728 E.02365
G1 X249.709 Y32.371 E.02365
; LINE_WIDTH: 0.402985
G1 F12497.745
G1 X249.777 Y32.783 E.01225
; LINE_WIDTH: 0.352023
G1 F14558.265
G1 X249.845 Y33.194 E.01052
G1 X249.845 Y222.806 E4.77592
G1 X249.823 Y223.159 E.00893
; LINE_WIDTH: 0.38144
G1 F13293.16
G1 X249.766 Y223.394 E.00667
; LINE_WIDTH: 0.418261
G1 F11989.116
G1 X249.709 Y223.629 E.00739
G1 X249.272 Y224.272 E.02377
G1 X248.629 Y224.709 E.02377
; LINE_WIDTH: 0.407145
G1 F12355
G1 X248.394 Y224.766 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X247.806 Y224.845 I-.52 J-1.627 E.01504
G1 X8.254 Y224.845 E6.03379
G1 X8.194 Y224.502 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X7.52 Y224.363 E.02115
G1 X6.995 Y224.005 E.01954
G1 X6.637 Y223.48 E.01954
G3 X6.498 Y222.806 I1.557 J-.674 E.02129
G1 X6.498 Y33.194 E5.82608
G1 X6.637 Y32.52 E.02115
G1 X6.995 Y31.995 E.01954
G1 X7.52 Y31.637 E.01954
G3 X8.194 Y31.498 I.674 J1.557 E.02129
G1 X247.806 Y31.498 E7.3624
G1 X248.48 Y31.637 E.02115
G1 X249.005 Y31.995 E.01954
G1 X249.363 Y32.52 E.01954
G1 X249.502 Y33.194 E.02115
G1 X249.502 Y222.806 E5.82608
G3 X249.363 Y223.48 I-1.696 J0 E.02129
G1 X249.005 Y224.005 E.01954
G1 X248.48 Y224.363 E.01954
G3 X247.806 Y224.502 I-.674 J-1.557 E.02129
G1 X8.254 Y224.502 E7.36055
G1 X8.194 Y224.125 F36000
G1 F11934.123
G1 X7.67 Y224.017 E.01645
G1 X7.261 Y223.739 E.0152
G1 X6.983 Y223.33 E.0152
G3 X6.875 Y222.806 I1.211 J-.524 E.01656
G1 X6.875 Y33.194 E5.82608
G1 X6.983 Y32.67 E.01645
G1 X7.261 Y32.261 E.0152
G1 X7.67 Y31.983 E.0152
G3 X8.194 Y31.875 I.524 J1.211 E.01656
G1 X247.806 Y31.875 E7.3624
G1 X248.33 Y31.983 E.01645
G1 X248.739 Y32.261 E.0152
G1 X249.017 Y32.67 E.0152
G1 X249.125 Y33.194 E.01645
G1 X249.125 Y222.806 E5.82608
G3 X249.017 Y223.33 I-1.32 J0 E.01656
G1 X248.739 Y223.739 E.0152
G1 X248.33 Y224.017 E.0152
G3 X247.806 Y224.125 I-.524 J-1.211 E.01656
G1 X8.254 Y224.125 E7.36055
G1 X8.194 Y223.748 F36000
G1 F11934.123
G1 X7.82 Y223.671 E.01175
G1 X7.528 Y223.472 E.01085
G1 X7.329 Y223.18 E.01085
M73 P71 R6
G1 X7.252 Y222.806 E.01175
G1 X7.252 Y33.194 E5.82608
G1 X7.329 Y32.82 E.01175
G1 X7.528 Y32.528 E.01085
G1 X7.82 Y32.329 E.01085
G1 X8.194 Y32.252 E.01175
G1 X247.806 Y32.252 E7.3624
G1 X248.18 Y32.329 E.01175
G1 X248.472 Y32.528 E.01085
G1 X248.671 Y32.82 E.01085
G1 X248.748 Y33.194 E.01175
G1 X248.748 Y222.806 E5.82608
G1 X248.671 Y223.18 E.01175
G1 X248.472 Y223.472 E.01085
G1 X248.18 Y223.671 E.01085
G1 X247.806 Y223.748 E.01175
G1 X8.254 Y223.748 E7.36055
G1 X8.194 Y223.371 F36000
G1 F11934.123
G3 X7.794 Y223.206 I0 J-.566 E.01365
G1 X7.637 Y222.903 E.01047
G1 X7.629 Y222.806 E.00301
G1 X7.629 Y33.194 E5.82608
G3 X7.794 Y32.794 I.566 J0 E.01365
G1 X8.097 Y32.637 E.01047
G1 X8.194 Y32.629 E.00301
G1 X247.806 Y32.629 E7.3624
G3 X248.371 Y33.194 I0 J.566 E.0273
G1 X248.371 Y222.806 E5.82608
G3 X248.206 Y223.206 I-.566 J0 E.01365
G1 X247.903 Y223.363 E.01047
G1 X247.806 Y223.371 E.00301
G1 X8.254 Y223.371 E7.36055
G1 X8.194 Y222.994 F36000
G1 F11934.123
G1 X8.061 Y222.939 E.00443
G1 X8.006 Y222.806 E.00443
G1 X8.006 Y33.194 E5.82608
G1 X8.061 Y33.061 E.00443
G1 X8.194 Y33.006 E.00443
G1 X247.806 Y33.006 E7.3624
G1 X247.939 Y33.061 E.00443
G1 X247.994 Y33.194 E.00443
G1 X247.994 Y222.806 E5.82608
G1 X247.939 Y222.939 E.00443
G1 X247.806 Y222.994 E.00443
G1 X8.254 Y222.994 E7.36055
G1 X6.873 Y31.222 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
M73 P72 R6
G1 X6.222 Y31.222 E.01636
G1 X6.222 Y31.873 E.01636
G1 X6.486 Y31.486 E.01178
G1 X6.823 Y31.256 E.01027
; CHANGE_LAYER
; Z_HEIGHT: 0.8
; LAYER_HEIGHT: 0.2
; WIPE_START
G1 F14588.129
G1 X6.486 Y31.486 E-.15521
G1 X6.222 Y31.873 E-.17801
G1 X6.222 Y31.222 E-.24729
G1 X6.695 Y31.222 E-.17949
; WIPE_END
G1 E-.04 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====





; update layer progress
M73 L4
M991 S0 P3 ;notify layer change


; OBJECT_ID: 15
G17
G3 Z1 I-.013 J1.217 P1  F36000
G1 X247.602 Y33.79 Z1
G1 Z.8
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X247.602 Y33.398 E.01301
G1 X8.398 Y33.398 E7.93484
G1 X8.398 Y222.602 E6.27625
G1 X247.602 Y222.602 E7.93484
G1 X247.602 Y33.85 E6.26125
M204 S250
G1 X247.21 Y33.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
M73 P72 R5
G1 X8.79 Y33.79 E7.32598
G1 X8.79 Y222.21 E5.78962
G1 X247.21 Y222.21 E7.32598
G1 X247.21 Y33.85 E5.78778
; WIPE_START
M204 S10000
G1 X245.21 Y33.849 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X245.493 Y41.477 Z1.2 F36000
G1 X252.398 Y227.398 Z1.2
G1 Z.8
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X252.398 Y28.602 E6.59442
G1 X3.602 Y28.602 E8.25302
G1 X3.602 Y227.398 E6.59442
G1 X252.338 Y227.398 E8.25103
M204 S250
G1 X252.79 Y227.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
M73 P73 R5
G1 X252.79 Y28.21 E6.13254
G1 X3.21 Y28.21 E7.6689
G1 X3.21 Y227.79 E6.13254
G1 X252.73 Y227.79 E7.66705
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

; WIPE_START
M204 S10000
G1 X252.731 Y225.79 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X249.127 Y31.222 F36000
G1 Z1.2
G1 Z.8
G1 E.8 F1800
; FEATURE: Internal solid infill
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.514 Y31.486 E.01178
G1 X249.778 Y31.873 E.01178
G1 X249.778 Y31.222 E.01636
G1 X249.187 Y31.222 E.01485
G1 X250.498 Y31.376 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X250.498 Y30.502 E.02686
G1 X5.502 Y30.502 E7.52783
G1 X5.502 Y225.498 E5.9915
G1 X250.498 Y225.498 E7.52783
G1 X250.498 Y31.436 E5.9628
G1 X250.875 Y31.376 F36000
G1 F11934.123
G1 X250.875 Y30.125 E.03844
G1 X5.125 Y30.125 E7.551
G1 X5.125 Y225.875 E6.01468
M73 P74 R5
G1 X250.875 Y225.875 E7.551
G1 X250.875 Y31.436 E5.97439
G1 X251.252 Y31.376 F36000
G1 F11934.123
G1 X251.252 Y29.748 E.05003
G1 X4.748 Y29.748 E7.57417
G1 X4.748 Y226.252 E6.03785
G1 X251.252 Y226.252 E7.57417
G1 X251.252 Y31.436 E5.98598
G1 X251.629 Y31.376 F36000
G1 F11934.123
G1 X251.629 Y29.371 E.06162
G1 X4.371 Y29.371 E7.59734
G1 X4.371 Y226.629 E6.06102
G1 X251.629 Y226.629 E7.59734
G1 X251.629 Y31.436 E5.99756
G1 X252.006 Y31.376 F36000
G1 F11934.123
G1 X252.006 Y28.994 E.0732
G1 X3.994 Y28.994 E7.62052
M73 P75 R5
G1 X3.994 Y227.006 E6.08419
G1 X252.006 Y227.006 E7.62052
G1 X252.006 Y31.436 E6.00915
G1 X249.127 Y224.778 F36000
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.778 Y224.778 E.01636
G1 X249.778 Y224.127 E.01636
G1 X249.514 Y224.514 E.01178
G1 X249.177 Y224.744 E.01027
G1 X247.806 Y225.155 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.26 Y225.138 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.514
G3 X250.121 Y225.121 I1.157 J24.86 E.05682
G1 X250.121 Y223.715 E.04293
; LINE_WIDTH: 0.40714
G1 F12355.17
G1 X250.133 Y223.451 E.00783
; LINE_WIDTH: 0.352028
G1 F14558.041
G2 X250.155 Y222.806 I-11.946 J-.715 E.01627
G1 X250.155 Y33.194 E4.77599
; LINE_WIDTH: 0.368975
G1 F13801.353
G1 X250.138 Y32.74 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.526
G3 X250.121 Y30.879 I49.729 J-1.385 E.05681
G1 X248.715 Y30.879 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X248.26 Y30.862 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X247.806 Y30.845 E.01145
G1 X8.194 Y30.845 E6.03511
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.74 Y30.862 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y30.879 I-1.158 J-24.87 E.05682
G1 X5.879 Y32.285 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X5.862 Y32.74 E.01334
; LINE_WIDTH: 0.352021
G1 F14558.364
G1 X5.845 Y33.194 E.01146
G1 X5.845 Y222.806 E4.77589
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X5.862 Y223.26 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y225.121 I-24.87 J1.158 E.05682
G1 X7.285 Y225.121 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X7.74 Y225.138 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X8.194 Y225.155 E.01145
G1 X247.746 Y225.155 E6.0336
G1 X6.873 Y224.778 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.486 Y224.514 E.01178
G1 X6.222 Y224.127 E.01178
G1 X6.222 Y224.778 E.01636
G1 X6.813 Y224.778 E.01485
G1 X8.194 Y224.845 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.783 Y224.777 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X7.371 Y224.709 E.0127
G1 X6.728 Y224.272 E.02365
G1 X6.291 Y223.629 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X6.234 Y223.394 E.00717
; LINE_WIDTH: 0.352033
G1 F14557.786
G3 X6.155 Y222.806 I1.627 J-.52 E.01504
G1 X6.155 Y33.194 E4.77608
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X6.223 Y32.783 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X6.291 Y32.371 E.0127
G1 X6.728 Y31.728 E.02365
G1 X7.371 Y31.291 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X7.606 Y31.234 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X8.194 Y31.155 I.52 J1.627 E.01504
G1 X247.806 Y31.155 E6.0353
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.217 Y31.223 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X248.629 Y31.291 E.0127
G1 X249.272 Y31.728 E.02365
G1 X249.709 Y32.371 E.02365
; LINE_WIDTH: 0.402985
G1 F12497.745
G1 X249.777 Y32.783 E.01225
; LINE_WIDTH: 0.352023
G1 F14558.265
G1 X249.845 Y33.194 E.01052
G1 X249.845 Y222.806 E4.77592
G1 X249.823 Y223.159 E.00893
; LINE_WIDTH: 0.38144
G1 F13293.16
G1 X249.766 Y223.394 E.00667
; LINE_WIDTH: 0.418261
G1 F11989.116
G1 X249.709 Y223.629 E.00739
M73 P76 R5
G1 X249.272 Y224.272 E.02377
G1 X248.629 Y224.709 E.02377
; LINE_WIDTH: 0.407145
G1 F12355
G1 X248.394 Y224.766 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X247.806 Y224.845 I-.52 J-1.627 E.01504
G1 X8.254 Y224.845 E6.03379
G1 X8.194 Y224.502 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X7.52 Y224.363 E.02115
G1 X6.995 Y224.005 E.01954
G1 X6.637 Y223.48 E.01954
G3 X6.498 Y222.806 I1.557 J-.674 E.02129
G1 X6.498 Y33.194 E5.82608
G1 X6.637 Y32.52 E.02115
G1 X6.995 Y31.995 E.01954
G1 X7.52 Y31.637 E.01954
G3 X8.194 Y31.498 I.674 J1.557 E.02129
G1 X247.806 Y31.498 E7.3624
G1 X248.48 Y31.637 E.02115
G1 X249.005 Y31.995 E.01954
G1 X249.363 Y32.52 E.01954
G1 X249.502 Y33.194 E.02115
G1 X249.502 Y222.806 E5.82608
G3 X249.363 Y223.48 I-1.696 J0 E.02129
G1 X249.005 Y224.005 E.01954
G1 X248.48 Y224.363 E.01954
G3 X247.806 Y224.502 I-.674 J-1.557 E.02129
G1 X8.254 Y224.502 E7.36055
G1 X8.194 Y224.125 F36000
G1 F11934.123
G1 X7.67 Y224.017 E.01645
G1 X7.261 Y223.739 E.0152
G1 X6.983 Y223.33 E.0152
G3 X6.875 Y222.806 I1.211 J-.524 E.01656
G1 X6.875 Y33.194 E5.82608
G1 X6.983 Y32.67 E.01645
G1 X7.261 Y32.261 E.0152
G1 X7.67 Y31.983 E.0152
G3 X8.194 Y31.875 I.524 J1.211 E.01656
G1 X247.806 Y31.875 E7.3624
G1 X248.33 Y31.983 E.01645
G1 X248.739 Y32.261 E.0152
G1 X249.017 Y32.67 E.0152
G1 X249.125 Y33.194 E.01645
G1 X249.125 Y222.806 E5.82608
G3 X249.017 Y223.33 I-1.32 J0 E.01656
G1 X248.739 Y223.739 E.0152
G1 X248.33 Y224.017 E.0152
G3 X247.806 Y224.125 I-.524 J-1.211 E.01656
G1 X8.254 Y224.125 E7.36055
G1 X8.194 Y223.748 F36000
G1 F11934.123
G1 X7.82 Y223.671 E.01175
G1 X7.528 Y223.472 E.01085
G1 X7.329 Y223.18 E.01085
G1 X7.252 Y222.806 E.01175
G1 X7.252 Y33.194 E5.82608
G1 X7.329 Y32.82 E.01175
G1 X7.528 Y32.528 E.01085
G1 X7.82 Y32.329 E.01085
G1 X8.194 Y32.252 E.01175
G1 X247.806 Y32.252 E7.3624
M73 P76 R4
G1 X248.18 Y32.329 E.01175
G1 X248.472 Y32.528 E.01085
G1 X248.671 Y32.82 E.01085
G1 X248.748 Y33.194 E.01175
G1 X248.748 Y222.806 E5.82608
M73 P77 R4
G1 X248.671 Y223.18 E.01175
G1 X248.472 Y223.472 E.01085
G1 X248.18 Y223.671 E.01085
G1 X247.806 Y223.748 E.01175
G1 X8.254 Y223.748 E7.36055
G1 X8.194 Y223.371 F36000
G1 F11934.123
G3 X7.794 Y223.206 I0 J-.566 E.01365
G1 X7.637 Y222.903 E.01047
G1 X7.629 Y222.806 E.00301
G1 X7.629 Y33.194 E5.82608
G3 X7.794 Y32.794 I.566 J0 E.01365
G1 X8.097 Y32.637 E.01047
G1 X8.194 Y32.629 E.00301
G1 X247.806 Y32.629 E7.3624
G3 X248.371 Y33.194 I0 J.566 E.0273
G1 X248.371 Y222.806 E5.82608
G3 X248.206 Y223.206 I-.566 J0 E.01365
G1 X247.903 Y223.363 E.01047
G1 X247.806 Y223.371 E.00301
G1 X8.254 Y223.371 E7.36055
G1 X8.194 Y222.994 F36000
G1 F11934.123
G1 X8.061 Y222.939 E.00443
G1 X8.006 Y222.806 E.00443
G1 X8.006 Y33.194 E5.82608
G1 X8.061 Y33.061 E.00443
G1 X8.194 Y33.006 E.00443
G1 X247.806 Y33.006 E7.3624
G1 X247.939 Y33.061 E.00443
G1 X247.994 Y33.194 E.00443
G1 X247.994 Y222.806 E5.82608
G1 X247.939 Y222.939 E.00443
G1 X247.806 Y222.994 E.00443
G1 X8.254 Y222.994 E7.36055
G1 X6.873 Y31.222 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.222 Y31.222 E.01636
G1 X6.222 Y31.873 E.01636
G1 X6.486 Y31.486 E.01178
G1 X6.823 Y31.256 E.01027
; CHANGE_LAYER
; Z_HEIGHT: 1
; LAYER_HEIGHT: 0.2
; WIPE_START
G1 F14588.129
G1 X6.486 Y31.486 E-.15521
G1 X6.222 Y31.873 E-.17801
G1 X6.222 Y31.222 E-.24729
G1 X6.695 Y31.222 E-.17949
; WIPE_END
G1 E-.04 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====





; update layer progress
M73 L5
M991 S0 P4 ;notify layer change


; OBJECT_ID: 15
G17
G3 Z1.2 I-.013 J1.217 P1  F36000
G1 X247.602 Y33.79 Z1.2
G1 Z1
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X247.602 Y33.398 E.01301
G1 X8.398 Y33.398 E7.93484
G1 X8.398 Y222.602 E6.27625
G1 X247.602 Y222.602 E7.93484
G1 X247.602 Y33.85 E6.26125
M204 S250
G1 X247.21 Y33.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
M73 P78 R4
G1 X8.79 Y33.79 E7.32598
G1 X8.79 Y222.21 E5.78962
G1 X247.21 Y222.21 E7.32598
G1 X247.21 Y33.85 E5.78778
; WIPE_START
M204 S10000
G1 X245.21 Y33.849 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X245.493 Y41.477 Z1.4 F36000
G1 X252.398 Y227.398 Z1.4
G1 Z1
G1 E.8 F1800
; FEATURE: Inner wall
; LINE_WIDTH: 0.45
G1 F11054.348
G1 X252.398 Y28.602 E6.59442
G1 X3.602 Y28.602 E8.25302
G1 X3.602 Y227.398 E6.59442
G1 X252.338 Y227.398 E8.25103
M204 S250
G1 X252.79 Y227.79 F36000
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X252.79 Y28.21 E6.13254
G1 X3.21 Y28.21 E7.6689
G1 X3.21 Y227.79 E6.13254
M73 P79 R4
G1 X252.73 Y227.79 E7.66705
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

; WIPE_START
M204 S10000
G1 X252.731 Y225.79 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X249.127 Y31.222 F36000
G1 Z1.4
G1 Z1
G1 E.8 F1800
; FEATURE: Internal solid infill
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.514 Y31.486 E.01178
G1 X249.778 Y31.873 E.01178
G1 X249.778 Y31.222 E.01636
G1 X249.187 Y31.222 E.01485
G1 X250.498 Y31.376 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X250.498 Y30.502 E.02686
G1 X5.502 Y30.502 E7.52783
G1 X5.502 Y225.498 E5.9915
G1 X250.498 Y225.498 E7.52783
G1 X250.498 Y31.436 E5.9628
G1 X250.875 Y31.376 F36000
G1 F11934.123
G1 X250.875 Y30.125 E.03844
G1 X5.125 Y30.125 E7.551
G1 X5.125 Y225.875 E6.01468
G1 X250.875 Y225.875 E7.551
G1 X250.875 Y31.436 E5.97439
G1 X251.252 Y31.376 F36000
G1 F11934.123
G1 X251.252 Y29.748 E.05003
M73 P80 R4
G1 X4.748 Y29.748 E7.57417
G1 X4.748 Y226.252 E6.03785
G1 X251.252 Y226.252 E7.57417
G1 X251.252 Y31.436 E5.98598
G1 X251.629 Y31.376 F36000
G1 F11934.123
G1 X251.629 Y29.371 E.06162
G1 X4.371 Y29.371 E7.59734
G1 X4.371 Y226.629 E6.06102
G1 X251.629 Y226.629 E7.59734
G1 X251.629 Y31.436 E5.99756
G1 X252.006 Y31.376 F36000
G1 F11934.123
G1 X252.006 Y28.994 E.0732
G1 X3.994 Y28.994 E7.62052
G1 X3.994 Y227.006 E6.08419
G1 X252.006 Y227.006 E7.62052
G1 X252.006 Y31.436 E6.00915
G1 X249.127 Y224.778 F36000
; LINE_WIDTH: 0.35141
G1 F14587.184
G1 X249.778 Y224.778 E.01636
M73 P81 R4
G1 X249.778 Y224.127 E.01636
G1 X249.514 Y224.514 E.01178
G1 X249.177 Y224.744 E.01027
G1 X247.806 Y225.155 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.26 Y225.138 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.514
G3 X250.121 Y225.121 I1.157 J24.86 E.05682
G1 X250.121 Y223.715 E.04293
; LINE_WIDTH: 0.40714
G1 F12355.17
G1 X250.133 Y223.451 E.00783
; LINE_WIDTH: 0.352028
G1 F14558.041
G2 X250.155 Y222.806 I-11.946 J-.715 E.01627
G1 X250.155 Y33.194 E4.77599
; LINE_WIDTH: 0.368975
G1 F13801.353
G1 X250.138 Y32.74 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.526
G3 X250.121 Y30.879 I49.729 J-1.385 E.05681
G1 X248.715 Y30.879 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X248.26 Y30.862 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X247.806 Y30.845 E.01145
G1 X8.194 Y30.845 E6.03511
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.74 Y30.862 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y30.879 I-1.158 J-24.87 E.05682
G1 X5.879 Y32.285 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X5.862 Y32.74 E.01334
; LINE_WIDTH: 0.352021
G1 F14558.364
G1 X5.845 Y33.194 E.01146
G1 X5.845 Y222.806 E4.77589
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X5.862 Y223.26 E.01208
; LINE_WIDTH: 0.417623
G1 F12009.516
G3 X5.879 Y225.121 I-24.87 J1.158 E.05682
G1 X7.285 Y225.121 E.04293
; LINE_WIDTH: 0.402988
G1 F12497.657
G1 X7.74 Y225.138 E.01334
; LINE_WIDTH: 0.352013
G1 F14558.762
G1 X8.194 Y225.155 E.01145
G1 X247.746 Y225.155 E6.0336
G1 X6.873 Y224.778 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.486 Y224.514 E.01178
G1 X6.222 Y224.127 E.01178
G1 X6.222 Y224.778 E.01636
M73 P81 R3
G1 X6.813 Y224.778 E.01485
G1 X8.194 Y224.845 F36000
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X7.783 Y224.777 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X7.371 Y224.709 E.0127
G1 X6.728 Y224.272 E.02365
G1 X6.291 Y223.629 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X6.234 Y223.394 E.00717
; LINE_WIDTH: 0.352033
G1 F14557.786
G3 X6.155 Y222.806 I1.627 J-.52 E.01504
G1 X6.155 Y33.194 E4.77608
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X6.223 Y32.783 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X6.291 Y32.371 E.0127
G1 X6.728 Y31.728 E.02365
G1 X7.371 Y31.291 E.02365
; LINE_WIDTH: 0.407145
G1 F12355
G1 X7.606 Y31.234 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X8.194 Y31.155 I.52 J1.627 E.01504
G1 X247.806 Y31.155 E6.0353
; LINE_WIDTH: 0.368983
G1 F13801.036
G1 X248.217 Y31.223 E.01109
; LINE_WIDTH: 0.416391
G1 F12049.155
G1 X248.629 Y31.291 E.0127
G1 X249.272 Y31.728 E.02365
G1 X249.709 Y32.371 E.02365
; LINE_WIDTH: 0.402985
G1 F12497.745
G1 X249.777 Y32.783 E.01225
; LINE_WIDTH: 0.352023
G1 F14558.265
G1 X249.845 Y33.194 E.01052
G1 X249.845 Y222.806 E4.77592
G1 X249.823 Y223.159 E.00893
; LINE_WIDTH: 0.38144
G1 F13293.16
G1 X249.766 Y223.394 E.00667
; LINE_WIDTH: 0.418261
G1 F11989.116
G1 X249.709 Y223.629 E.00739
G1 X249.272 Y224.272 E.02377
G1 X248.629 Y224.709 E.02377
; LINE_WIDTH: 0.407145
G1 F12355
G1 X248.394 Y224.766 E.00717
; LINE_WIDTH: 0.352022
G1 F14558.305
G3 X247.806 Y224.845 I-.52 J-1.627 E.01504
G1 X8.254 Y224.845 E6.03379
G1 X8.194 Y224.502 F36000
; LINE_WIDTH: 0.41999
G1 F11934.123
G1 X7.52 Y224.363 E.02115
G1 X6.995 Y224.005 E.01954
G1 X6.637 Y223.48 E.01954
G3 X6.498 Y222.806 I1.557 J-.674 E.02129
G1 X6.498 Y33.194 E5.82608
G1 X6.637 Y32.52 E.02115
G1 X6.995 Y31.995 E.01954
G1 X7.52 Y31.637 E.01954
G3 X8.194 Y31.498 I.674 J1.557 E.02129
G1 X247.806 Y31.498 E7.3624
G1 X248.48 Y31.637 E.02115
G1 X249.005 Y31.995 E.01954
G1 X249.363 Y32.52 E.01954
G1 X249.502 Y33.194 E.02115
G1 X249.502 Y222.806 E5.82608
M73 P82 R3
G3 X249.363 Y223.48 I-1.696 J0 E.02129
G1 X249.005 Y224.005 E.01954
G1 X248.48 Y224.363 E.01954
G3 X247.806 Y224.502 I-.674 J-1.557 E.02129
G1 X8.254 Y224.502 E7.36055
G1 X8.194 Y224.125 F36000
G1 F11934.123
G1 X7.67 Y224.017 E.01645
G1 X7.261 Y223.739 E.0152
G1 X6.983 Y223.33 E.0152
G3 X6.875 Y222.806 I1.211 J-.524 E.01656
G1 X6.875 Y33.194 E5.82608
G1 X6.983 Y32.67 E.01645
G1 X7.261 Y32.261 E.0152
G1 X7.67 Y31.983 E.0152
G3 X8.194 Y31.875 I.524 J1.211 E.01656
G1 X247.806 Y31.875 E7.3624
G1 X248.33 Y31.983 E.01645
G1 X248.739 Y32.261 E.0152
G1 X249.017 Y32.67 E.0152
G1 X249.125 Y33.194 E.01645
G1 X249.125 Y222.806 E5.82608
G3 X249.017 Y223.33 I-1.32 J0 E.01656
G1 X248.739 Y223.739 E.0152
G1 X248.33 Y224.017 E.0152
G3 X247.806 Y224.125 I-.524 J-1.211 E.01656
G1 X8.254 Y224.125 E7.36055
G1 X8.194 Y223.748 F36000
G1 F11934.123
G1 X7.82 Y223.671 E.01175
G1 X7.528 Y223.472 E.01085
G1 X7.329 Y223.18 E.01085
G1 X7.252 Y222.806 E.01175
G1 X7.252 Y33.194 E5.82608
G1 X7.329 Y32.82 E.01175
G1 X7.528 Y32.528 E.01085
G1 X7.82 Y32.329 E.01085
G1 X8.194 Y32.252 E.01175
G1 X247.806 Y32.252 E7.3624
G1 X248.18 Y32.329 E.01175
G1 X248.472 Y32.528 E.01085
G1 X248.671 Y32.82 E.01085
G1 X248.748 Y33.194 E.01175
G1 X248.748 Y222.806 E5.82608
G1 X248.671 Y223.18 E.01175
G1 X248.472 Y223.472 E.01085
G1 X248.18 Y223.671 E.01085
G1 X247.806 Y223.748 E.01175
G1 X8.254 Y223.748 E7.36055
G1 X8.194 Y223.371 F36000
G1 F11934.123
G3 X7.794 Y223.206 I0 J-.566 E.01365
G1 X7.637 Y222.903 E.01047
G1 X7.629 Y222.806 E.00301
G1 X7.629 Y33.194 E5.82608
G3 X7.794 Y32.794 I.566 J0 E.01365
G1 X8.097 Y32.637 E.01047
G1 X8.194 Y32.629 E.00301
G1 X247.806 Y32.629 E7.3624
G3 X248.371 Y33.194 I0 J.566 E.0273
M73 P83 R3
G1 X248.371 Y222.806 E5.82608
G3 X248.206 Y223.206 I-.566 J0 E.01365
G1 X247.903 Y223.363 E.01047
G1 X247.806 Y223.371 E.00301
G1 X8.254 Y223.371 E7.36055
G1 X8.194 Y222.994 F36000
G1 F11934.123
G1 X8.061 Y222.939 E.00443
G1 X8.006 Y222.806 E.00443
G1 X8.006 Y33.194 E5.82608
G1 X8.061 Y33.061 E.00443
G1 X8.194 Y33.006 E.00443
G1 X247.806 Y33.006 E7.3624
G1 X247.939 Y33.061 E.00443
G1 X247.994 Y33.194 E.00443
G1 X247.994 Y222.806 E5.82608
G1 X247.939 Y222.939 E.00443
G1 X247.806 Y222.994 E.00443
G1 X8.254 Y222.994 E7.36055
G1 X6.873 Y31.222 F36000
; LINE_WIDTH: 0.35139
G1 F14588.129
G1 X6.222 Y31.222 E.01636
G1 X6.222 Y31.873 E.01636
G1 X6.486 Y31.486 E.01178
G1 X6.823 Y31.256 E.01027
; CHANGE_LAYER
; Z_HEIGHT: 1.2
; LAYER_HEIGHT: 0.2
; WIPE_START
G1 F14588.129
G1 X6.486 Y31.486 E-.15521
G1 X6.222 Y31.873 E-.17801
G1 X6.222 Y31.222 E-.24729
G1 X6.695 Y31.222 E-.17949
; WIPE_END
G1 E-.04 F1800
;======== P2S layer_change gcode ==========
;===== 2026/05/15 ====





; update layer progress
M73 L6
M991 S0 P5 ;notify layer change


; OBJECT_ID: 15
G17
G3 Z1.4 I-.013 J1.217 P1  F36000
G1 X247.21 Y33.79 Z1.4
G1 Z1.2
G1 E.8 F1800
; FEATURE: Outer wall
; LINE_WIDTH: 0.42
G1 F11933.819
M204 S6000
G1 X8.79 Y33.79 E7.32598
G1 X8.79 Y222.21 E5.78962
G1 X247.21 Y222.21 E7.32598
G1 X247.21 Y33.85 E5.78778
; WIPE_START
M204 S10000
G1 X245.21 Y33.849 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X245.508 Y41.476 Z1.6 F36000
G1 X252.79 Y227.79 Z1.6
G1 Z1.2
M73 P84 R3
G1 E.8 F1800
G1 F11933.819
M204 S6000
G1 X252.79 Y28.21 E6.13254
G1 X3.21 Y28.21 E7.6689
G1 X3.21 Y227.79 E6.13254
G1 X252.73 Y227.79 E7.66705
;======== P2S timelapes gcode ==========
;===== 2025/06/16 ====
; SKIPPABLE_START
; SKIPTYPE: timelapse
M622.1 S1 ; for prev firware, default turned on

M1002 judge_flag timelapse_record_flag
M622 J1
 ; timelapse without wipe tower
  M971 S11 C10 O0
  M1004 S5 P1  ; external shutter

M623
; SKIPPABLE_END

M204 S10000
G1 X252.119 Y227.583 F36000
; FEATURE: Top surface
G1 F11933.819
M204 S2000
G1 X252.583 Y227.119 E.02015
G1 X252.716 Y226.985
G1 X252.716 Y226.452
G1 X252.583 Y226.586
G1 X251.586 Y227.583 E.04333
G1 X251.452 Y227.716
G1 X250.919 Y227.716
G1 X251.052 Y227.583
G1 X252.583 Y226.052 E.0665
G1 X252.716 Y225.919
G1 X252.716 Y225.385
G1 X252.583 Y225.519
G1 X250.519 Y227.583 E.08967
G1 X250.385 Y227.716
G1 X249.852 Y227.716
G1 X249.986 Y227.583
G1 X252.583 Y224.986 E.11284
G1 X252.716 Y224.852
G1 X252.716 Y224.319
G1 X252.583 Y224.453
G1 X249.453 Y227.583 E.13602
G1 X249.319 Y227.716
G1 X248.786 Y227.716
G1 X248.919 Y227.583
G1 X252.583 Y223.919 E.15919
G1 X252.716 Y223.786
G1 X252.716 Y223.252
G1 X252.583 Y223.386
G1 X248.386 Y227.583 E.18236
G1 X248.252 Y227.716
G1 X247.719 Y227.716
G1 X247.853 Y227.583
G1 X252.583 Y222.853 E.20553
G1 X252.716 Y222.719
G1 X252.716 Y222.186
G1 X252.583 Y222.32
G1 X247.32 Y227.583 E.22871
G1 X247.186 Y227.716
G1 X246.653 Y227.716
G1 X246.786 Y227.583
G1 X252.583 Y221.786 E.25188
G1 X252.716 Y221.653
G1 X252.716 Y221.119
G1 X252.583 Y221.253
G1 X246.253 Y227.583 E.27505
G1 X246.119 Y227.716
G1 X245.586 Y227.716
G1 X245.72 Y227.583
G1 X252.583 Y220.72 E.29823
G1 X252.716 Y220.586
G1 X252.716 Y220.053
G1 X252.583 Y220.186
G1 X245.186 Y227.583 E.3214
G1 X245.053 Y227.716
G1 X244.52 Y227.716
G1 X244.653 Y227.583
G1 X252.583 Y219.653 E.34457
G1 X252.716 Y219.52
G1 X252.716 Y218.986
G1 X252.583 Y219.12
G1 X244.12 Y227.583 E.36774
G1 X243.986 Y227.716
G1 X243.453 Y227.716
G1 X243.587 Y227.583
G1 X252.583 Y218.587 E.39092
G1 X252.716 Y218.453
G1 X252.716 Y217.92
G1 X252.583 Y218.053
G1 X243.053 Y227.583 E.41409
G1 X242.92 Y227.716
G1 X242.387 Y227.716
G1 X242.52 Y227.583
G1 X252.583 Y217.52 E.43726
G1 X252.716 Y217.387
G1 X252.716 Y216.853
G1 X252.583 Y216.987
G1 X247.417 Y222.152 E.22445
G1 X247.284 Y222.286
G1 X247.284 Y221.753
G1 X247.417 Y221.619
G1 X252.583 Y216.454 E.22445
G1 X252.716 Y216.32
G1 X252.716 Y215.787
G1 X252.583 Y215.92
G1 X247.417 Y221.086 E.22445
G1 X247.284 Y221.219
G1 X247.284 Y220.686
G1 X247.417 Y220.552
G1 X252.583 Y215.387 E.22445
G1 X252.716 Y215.254
G1 X252.716 Y214.72
G1 X252.583 Y214.854
G1 X247.417 Y220.019 E.22445
G1 X247.284 Y220.153
G1 X247.284 Y219.62
G1 X247.417 Y219.486
G1 X252.583 Y214.321 E.22445
G1 X252.716 Y214.187
G1 X252.716 Y213.654
G1 X252.583 Y213.787
G1 X247.417 Y218.953 E.22445
G1 X247.284 Y219.086
G1 X247.284 Y218.553
G1 X247.417 Y218.419
G1 X252.583 Y213.254 E.22445
G1 X252.716 Y213.12
G1 X252.716 Y212.587
G1 X252.583 Y212.721
G1 X247.417 Y217.886 E.22445
G1 X247.284 Y218.02
G1 X247.284 Y217.487
G1 X247.417 Y217.353
G1 X252.583 Y212.188 E.22445
G1 X252.716 Y212.054
G1 X252.716 Y211.521
G1 X252.583 Y211.654
G1 X247.417 Y216.82 E.22445
G1 X247.284 Y216.953
G1 X247.284 Y216.42
G1 X247.417 Y216.286
G1 X252.583 Y211.121 E.22445
G1 X252.716 Y210.987
G1 X252.716 Y210.454
G1 X252.583 Y210.588
G1 X247.417 Y215.753 E.22445
G1 X247.284 Y215.887
G1 X247.284 Y215.353
G1 X247.417 Y215.22
G1 X252.583 Y210.055 E.22445
G1 X252.716 Y209.921
G1 X252.716 Y209.388
G1 X252.583 Y209.521
G1 X247.417 Y214.687 E.22445
G1 X247.284 Y214.82
G1 X247.284 Y214.287
G1 X247.417 Y214.153
G1 X252.583 Y208.988 E.22445
G1 X252.716 Y208.854
G1 X252.716 Y208.321
G1 X252.583 Y208.455
G1 X247.417 Y213.62 E.22445
G1 X247.284 Y213.754
G1 X247.284 Y213.22
G1 X247.417 Y213.087
G1 X252.583 Y207.922 E.22445
G1 X252.716 Y207.788
G1 X252.716 Y207.255
G1 X252.583 Y207.388
G1 X247.417 Y212.554 E.22445
G1 X247.284 Y212.687
G1 X247.284 Y212.154
G1 X247.417 Y212.02
G1 X252.583 Y206.855 E.22445
G1 X252.716 Y206.721
G1 X252.716 Y206.188
G1 X252.583 Y206.322
G1 X247.417 Y211.487 E.22445
G1 X247.284 Y211.621
G1 X247.284 Y211.087
G1 X247.417 Y210.954
G1 X252.583 Y205.789 E.22445
G1 X252.716 Y205.655
G1 X252.716 Y205.122
G1 X252.583 Y205.255
G1 X247.417 Y210.421 E.22445
G1 X247.284 Y210.554
G1 X247.284 Y210.021
G1 X247.417 Y209.887
G1 X252.583 Y204.722 E.22445
G1 X252.716 Y204.588
G1 X252.716 Y204.055
G1 X252.583 Y204.189
G1 X247.417 Y209.354 E.22445
G1 X247.284 Y209.488
G1 X247.284 Y208.954
G1 X247.417 Y208.821
G1 X252.583 Y203.656 E.22445
G1 X252.716 Y203.522
G1 X252.716 Y202.989
G1 X252.583 Y203.122
G1 X247.417 Y208.287 E.22445
G1 X247.284 Y208.421
G1 X247.284 Y207.888
G1 X247.417 Y207.754
G1 X252.583 Y202.589 E.22445
G1 X252.716 Y202.455
G1 X252.716 Y201.922
G1 X252.583 Y202.056
G1 X247.417 Y207.221 E.22445
G1 X247.284 Y207.355
G1 X247.284 Y206.821
G1 X247.417 Y206.688
G1 X252.583 Y201.522 E.22445
G1 X252.716 Y201.389
G1 X252.716 Y200.856
G1 X252.583 Y200.989
G1 X247.417 Y206.154 E.22446
G1 X247.284 Y206.288
G1 X247.284 Y205.755
G1 X247.417 Y205.621
G1 X252.583 Y200.456 E.22445
G1 X252.716 Y200.322
G1 X252.716 Y199.789
G1 X252.583 Y199.923
G1 X247.417 Y205.088 E.22445
G1 X247.284 Y205.222
G1 X247.284 Y204.688
G1 X247.417 Y204.555
G1 X252.583 Y199.389 E.22446
G1 X252.716 Y199.256
G1 X252.716 Y198.723
G1 X252.583 Y198.856
G1 X247.417 Y204.021 E.22446
G1 X247.284 Y204.155
G1 X247.284 Y203.622
G1 X247.417 Y203.488
G1 X252.583 Y198.323 E.22445
G1 X252.716 Y198.189
G1 X252.716 Y197.656
G1 X252.583 Y197.79
G1 X247.417 Y202.955 E.22445
G1 X247.284 Y203.089
G1 X247.284 Y202.555
G1 X247.417 Y202.422
G1 X252.583 Y197.256 E.22446
G1 X252.716 Y197.123
G1 X252.716 Y196.59
G1 X252.583 Y196.723
G1 X247.417 Y201.888 E.22446
G1 X247.284 Y202.022
G1 X247.284 Y201.489
G1 X247.417 Y201.355
G1 X252.583 Y196.19 E.22445
G1 X252.716 Y196.056
G1 X252.716 Y195.523
G1 X252.583 Y195.657
G1 X247.417 Y200.822 E.22445
G1 X247.284 Y200.956
G1 X247.284 Y200.422
G1 X247.417 Y200.289
G1 X252.583 Y195.123 E.22446
G1 X252.716 Y194.99
G1 X252.716 Y194.456
G1 X252.583 Y194.59
G1 X247.417 Y199.755 E.22446
G1 X247.284 Y199.889
G1 X247.284 Y199.356
G1 X247.417 Y199.222
G1 X252.583 Y194.057 E.22445
G1 X252.716 Y193.923
G1 X252.716 Y193.39
G1 X252.583 Y193.524
G1 X247.417 Y198.689 E.22445
G1 X247.284 Y198.822
G1 X247.284 Y198.289
G1 X247.417 Y198.156
G1 X252.583 Y192.99 E.22446
G1 X252.716 Y192.857
G1 X252.716 Y192.323
G1 X252.583 Y192.457
M73 P85 R3
G1 X247.417 Y197.622 E.22446
G1 X247.284 Y197.756
G1 X247.284 Y197.223
G1 X247.417 Y197.089
G1 X252.583 Y191.924 E.22445
G1 X252.716 Y191.79
G1 X252.716 Y191.257
G1 X252.583 Y191.391
G1 X247.417 Y196.556 E.22445
G1 X247.284 Y196.689
G1 X247.284 Y196.156
G1 X247.417 Y196.023
G1 X252.583 Y190.857 E.22446
G1 X252.716 Y190.724
G1 X252.716 Y190.19
G1 X252.583 Y190.324
G1 X247.417 Y195.489 E.22446
G1 X247.284 Y195.623
G1 X247.284 Y195.09
G1 X247.417 Y194.956
G1 X252.583 Y189.791 E.22445
G1 X252.716 Y189.657
G1 X252.716 Y189.124
G1 X252.583 Y189.258
G1 X247.417 Y194.423 E.22445
G1 X247.284 Y194.556
G1 X247.284 Y194.023
G1 X247.417 Y193.89
G1 X252.583 Y188.724 E.22446
G1 X252.716 Y188.591
G1 X252.716 Y188.057
G1 X252.583 Y188.191
G1 X247.417 Y193.356 E.22446
G1 X247.284 Y193.49
G1 X247.284 Y192.957
G1 X247.417 Y192.823
G1 X252.583 Y187.658 E.22445
G1 X252.716 Y187.524
G1 X252.716 Y186.991
G1 X252.583 Y187.125
G1 X247.417 Y192.29 E.22445
G1 X247.284 Y192.423
G1 X247.284 Y191.89
G1 X247.417 Y191.757
G1 X252.583 Y186.591 E.22446
G1 X252.716 Y186.458
G1 X252.716 Y185.924
G1 X252.583 Y186.058
G1 X247.417 Y191.223 E.22446
G1 X247.284 Y191.357
G1 X247.284 Y190.824
G1 X247.417 Y190.69
G1 X252.583 Y185.525 E.22445
G1 X252.716 Y185.391
G1 X252.716 Y184.858
G1 X252.583 Y184.991
G1 X247.417 Y190.157 E.22445
G1 X247.284 Y190.29
G1 X247.284 Y189.757
G1 X247.417 Y189.623
G1 X252.583 Y184.458 E.22446
G1 X252.716 Y184.325
G1 X252.716 Y183.791
G1 X252.583 Y183.925
G1 X247.417 Y189.09 E.22446
G1 X247.284 Y189.224
G1 X247.284 Y188.691
G1 X247.417 Y188.557
G1 X252.583 Y183.392 E.22445
G1 X252.716 Y183.258
G1 X252.716 Y182.725
G1 X252.583 Y182.858
G1 X247.417 Y188.024 E.22445
G1 X247.284 Y188.157
G1 X247.284 Y187.624
G1 X247.417 Y187.49
G1 X252.583 Y182.325 E.22445
G1 X252.716 Y182.192
G1 X252.716 Y181.658
G1 X252.583 Y181.792
G1 X247.417 Y186.957 E.22445
G1 X247.284 Y187.091
G1 X247.284 Y186.558
G1 X247.417 Y186.424
G1 X252.583 Y181.259 E.22445
G1 X252.716 Y181.125
G1 X252.716 Y180.592
G1 X252.583 Y180.725
G1 X247.417 Y185.891 E.22445
G1 X247.284 Y186.024
G1 X247.284 Y185.491
G1 X247.417 Y185.357
G1 X252.583 Y180.192 E.22445
G1 X252.716 Y180.059
G1 X252.716 Y179.525
G1 X252.583 Y179.659
G1 X247.417 Y184.824 E.22445
G1 X247.284 Y184.958
G1 X247.284 Y184.425
G1 X247.417 Y184.291
G1 X252.583 Y179.126 E.22445
G1 X252.716 Y178.992
G1 X252.716 Y178.459
G1 X252.583 Y178.592
G1 X247.417 Y183.758 E.22445
G1 X247.284 Y183.891
G1 X247.284 Y183.358
G1 X247.417 Y183.224
G1 X252.583 Y178.059 E.22445
G1 X252.716 Y177.926
G1 X252.716 Y177.392
G1 X252.583 Y177.526
G1 X247.417 Y182.691 E.22445
G1 X247.284 Y182.825
G1 X247.284 Y182.292
G1 X247.417 Y182.158
G1 X252.583 Y176.993 E.22445
G1 X252.716 Y176.859
G1 X252.716 Y176.326
G1 X252.583 Y176.459
G1 X247.417 Y181.625 E.22445
G1 X247.284 Y181.758
G1 X247.284 Y181.225
G1 X247.417 Y181.091
G1 X252.583 Y175.926 E.22445
G1 X252.716 Y175.792
G1 X252.716 Y175.259
G1 X252.583 Y175.393
G1 X247.417 Y180.558 E.22445
G1 X247.284 Y180.692
G1 X247.284 Y180.158
G1 X247.417 Y180.025
G1 X252.583 Y174.86 E.22445
G1 X252.716 Y174.726
G1 X252.716 Y174.193
G1 X252.583 Y174.326
G1 X247.417 Y179.492 E.22445
G1 X247.284 Y179.625
G1 X247.284 Y179.092
G1 X247.417 Y178.958
G1 X252.583 Y173.793 E.22445
G1 X252.716 Y173.659
G1 X252.716 Y173.126
G1 X252.583 Y173.26
G1 X247.417 Y178.425 E.22445
G1 X247.284 Y178.559
G1 X247.284 Y178.025
G1 X247.417 Y177.892
G1 X252.583 Y172.727 E.22445
G1 X252.716 Y172.593
G1 X252.716 Y172.06
G1 X252.583 Y172.193
G1 X247.417 Y177.359 E.22445
G1 X247.284 Y177.492
G1 X247.284 Y176.959
G1 X247.417 Y176.825
G1 X252.583 Y171.66 E.22445
G1 X252.716 Y171.526
G1 X252.716 Y170.993
G1 X252.583 Y171.127
G1 X247.417 Y176.292 E.22445
G1 X247.284 Y176.426
G1 X247.284 Y175.892
G1 X247.417 Y175.759
G1 X252.583 Y170.594 E.22445
G1 X252.716 Y170.46
G1 X252.716 Y169.927
G1 X252.583 Y170.06
G1 X247.417 Y175.226 E.22445
G1 X247.284 Y175.359
G1 X247.284 Y174.826
G1 X247.417 Y174.692
G1 X252.583 Y169.527 E.22446
G1 X252.716 Y169.393
G1 X252.716 Y168.86
G1 X252.583 Y168.994
G1 X247.417 Y174.159 E.22446
G1 X247.284 Y174.293
G1 X247.284 Y173.759
G1 X247.417 Y173.626
G1 X252.583 Y168.461 E.22446
G1 X252.716 Y168.327
G1 X252.716 Y167.794
G1 X252.583 Y167.927
G1 X247.417 Y173.093 E.22446
G1 X247.284 Y173.226
G1 X247.284 Y172.693
G1 X247.417 Y172.559
G1 X252.583 Y167.394 E.22445
G1 X252.716 Y167.26
G1 X252.716 Y166.727
G1 X252.583 Y166.861
G1 X247.417 Y172.026 E.22445
G1 X247.284 Y172.16
G1 X247.284 Y171.626
G1 X247.417 Y171.493
G1 X252.583 Y166.327 E.22446
G1 X252.716 Y166.194
G1 X252.716 Y165.661
G1 X252.583 Y165.794
G1 X247.417 Y170.959 E.22445
G1 X247.284 Y171.093
G1 X247.284 Y170.56
G1 X247.417 Y170.426
G1 X252.583 Y165.261 E.22445
G1 X252.716 Y165.127
G1 X252.716 Y164.594
G1 X252.583 Y164.728
G1 X247.417 Y169.893 E.22445
G1 X247.284 Y170.027
G1 X247.284 Y169.493
G1 X247.417 Y169.36
G1 X252.583 Y164.194 E.22446
G1 X252.716 Y164.061
G1 X252.716 Y163.528
G1 X252.583 Y163.661
G1 X247.417 Y168.826 E.22446
G1 X247.284 Y168.96
G1 X247.284 Y168.427
G1 X247.417 Y168.293
G1 X252.583 Y163.128 E.22445
G1 X252.716 Y162.994
G1 X252.716 Y162.461
G1 X252.583 Y162.595
G1 X247.417 Y167.76 E.22445
G1 X247.284 Y167.894
G1 X247.284 Y167.36
G1 X247.417 Y167.227
G1 X252.583 Y162.061 E.22446
G1 X252.716 Y161.928
G1 X252.716 Y161.395
G1 X252.583 Y161.528
G1 X247.417 Y166.693 E.22446
G1 X247.284 Y166.827
G1 X247.284 Y166.294
G1 X247.417 Y166.16
G1 X252.583 Y160.995 E.22445
G1 X252.716 Y160.861
G1 X252.716 Y160.328
G1 X252.583 Y160.462
G1 X247.417 Y165.627 E.22445
G1 X247.284 Y165.761
G1 X247.284 Y165.227
G1 X247.417 Y165.094
G1 X252.583 Y159.928 E.22446
G1 X252.716 Y159.795
G1 X252.716 Y159.261
G1 X252.583 Y159.395
G1 X247.417 Y164.56 E.22446
G1 X247.284 Y164.694
G1 X247.284 Y164.161
G1 X247.417 Y164.027
G1 X252.583 Y158.862 E.22445
G1 X252.716 Y158.728
G1 X252.716 Y158.195
G1 X252.583 Y158.329
G1 X247.417 Y163.494 E.22445
G1 X247.284 Y163.628
G1 X247.284 Y163.094
G1 X247.417 Y162.961
G1 X252.583 Y157.795 E.22446
G1 X252.716 Y157.662
G1 X252.716 Y157.128
G1 X252.583 Y157.262
G1 X247.417 Y162.427 E.22446
G1 X247.284 Y162.561
G1 X247.284 Y162.028
G1 X247.417 Y161.894
G1 X252.583 Y156.729 E.22445
G1 X252.716 Y156.595
G1 X252.716 Y156.062
G1 X252.583 Y156.196
G1 X247.417 Y161.361 E.22445
G1 X247.284 Y161.494
G1 X247.284 Y160.961
G1 X247.417 Y160.828
G1 X252.583 Y155.662 E.22446
G1 X252.716 Y155.529
G1 X252.716 Y154.995
G1 X252.583 Y155.129
G1 X247.417 Y160.294 E.22446
G1 X247.284 Y160.428
G1 X247.284 Y159.895
G1 X247.417 Y159.761
G1 X252.583 Y154.596 E.22445
G1 X252.716 Y154.462
G1 X252.716 Y153.929
G1 X252.583 Y154.063
G1 X247.417 Y159.228 E.22445
G1 X247.284 Y159.361
G1 X247.284 Y158.828
G1 X247.417 Y158.695
G1 X252.583 Y153.529 E.22446
G1 X252.716 Y153.396
G1 X252.716 Y152.862
G1 X252.583 Y152.996
G1 X247.417 Y158.161 E.22446
G1 X247.284 Y158.295
G1 X247.284 Y157.762
G1 X247.417 Y157.628
G1 X252.583 Y152.463 E.22445
G1 X252.716 Y152.329
G1 X252.716 Y151.796
G1 X252.583 Y151.93
G1 X247.417 Y157.095 E.22445
G1 X247.284 Y157.228
G1 X247.284 Y156.695
G1 X247.417 Y156.562
G1 X252.583 Y151.396 E.22446
G1 X252.716 Y151.263
G1 X252.716 Y150.729
G1 X252.583 Y150.863
G1 X247.417 Y156.028 E.22446
G1 X247.284 Y156.162
G1 X247.284 Y155.629
G1 X247.417 Y155.495
G1 X252.583 Y150.33 E.22445
G1 X252.716 Y150.196
G1 X252.716 Y149.663
G1 X252.583 Y149.797
G1 X247.417 Y154.962 E.22445
G1 X247.284 Y155.095
G1 X247.284 Y154.562
G1 X247.417 Y154.428
G1 X252.583 Y149.263 E.22446
G1 X252.716 Y149.13
G1 X252.716 Y148.596
G1 X252.583 Y148.73
G1 X247.417 Y153.895 E.22446
G1 X247.284 Y154.029
G1 X247.284 Y153.496
G1 X247.417 Y153.362
G1 X252.583 Y148.197 E.22445
G1 X252.716 Y148.063
G1 X252.716 Y147.53
G1 X252.583 Y147.663
G1 X247.417 Y152.829 E.22445
G1 X247.284 Y152.962
G1 X247.284 Y152.429
G1 X247.417 Y152.295
G1 X252.583 Y147.13 E.22446
G1 X252.716 Y146.997
G1 X252.716 Y146.463
G1 X252.583 Y146.597
G1 X247.417 Y151.762 E.22446
G1 X247.284 Y151.896
G1 X247.284 Y151.363
G1 X247.417 Y151.229
G1 X252.583 Y146.064 E.22445
G1 X252.716 Y145.93
G1 X252.716 Y145.397
G1 X252.583 Y145.53
G1 X247.417 Y150.696 E.22445
G1 X247.284 Y150.829
G1 X247.284 Y150.296
G1 X247.417 Y150.162
G1 X252.583 Y144.997 E.22446
G1 X252.716 Y144.864
G1 X252.716 Y144.33
G1 X252.583 Y144.464
G1 X247.417 Y149.629 E.22446
G1 X247.284 Y149.763
G1 X247.284 Y149.23
G1 X247.417 Y149.096
G1 X252.583 Y143.931 E.22445
G1 X252.716 Y143.797
G1 X252.716 Y143.264
G1 X252.583 Y143.397
G1 X247.417 Y148.563 E.22445
G1 X247.284 Y148.696
G1 X247.284 Y148.163
G1 X247.417 Y148.029
G1 X252.583 Y142.864 E.22446
G1 X252.716 Y142.731
G1 X252.716 Y142.197
G1 X252.583 Y142.331
G1 X247.417 Y147.496 E.22446
G1 X247.284 Y147.63
G1 X247.284 Y147.097
G1 X247.417 Y146.963
G1 X252.583 Y141.798 E.22445
G1 X252.716 Y141.664
G1 X252.716 Y141.131
G1 X252.583 Y141.264
G1 X247.417 Y146.43 E.22445
G1 X247.284 Y146.563
G1 X247.284 Y146.03
G1 X247.417 Y145.896
G1 X252.583 Y140.731 E.22445
G1 X252.716 Y140.597
G1 X252.716 Y140.064
G1 X252.583 Y140.198
G1 X247.417 Y145.363 E.22445
G1 X247.284 Y145.497
G1 X247.284 Y144.963
G1 X247.417 Y144.83
G1 X252.583 Y139.665 E.22445
G1 X252.716 Y139.531
G1 X252.716 Y138.998
G1 X252.583 Y139.131
G1 X247.417 Y144.297 E.22445
G1 X247.284 Y144.43
G1 X247.284 Y143.897
G1 X247.417 Y143.763
G1 X252.583 Y138.598 E.22445
G1 X252.716 Y138.464
G1 X252.716 Y137.931
G1 X252.583 Y138.065
G1 X247.417 Y143.23 E.22446
G1 X247.284 Y143.364
G1 X247.284 Y142.83
G1 X247.417 Y142.697
G1 X252.583 Y137.532 E.22446
G1 X252.716 Y137.398
G1 X252.716 Y136.865
G1 X252.583 Y136.998
G1 X247.417 Y142.164 E.22446
G1 X247.284 Y142.297
G1 X247.284 Y141.764
G1 X247.417 Y141.63
G1 X252.583 Y136.465 E.22446
G1 X252.716 Y136.331
G1 X252.716 Y135.798
G1 X252.583 Y135.932
G1 X247.417 Y141.097 E.22446
G1 X247.284 Y141.231
G1 X247.284 Y140.697
G1 X247.417 Y140.564
G1 X252.583 Y135.399 E.22446
G1 X252.716 Y135.265
G1 X252.716 Y134.732
G1 X252.583 Y134.865
G1 X247.417 Y140.031 E.22446
G1 X247.284 Y140.164
G1 X247.284 Y139.631
G1 X247.417 Y139.497
G1 X252.583 Y134.332 E.22446
G1 X252.716 Y134.198
G1 X252.716 Y133.665
G1 X252.583 Y133.799
G1 X247.417 Y138.964 E.22446
G1 X247.284 Y139.098
G1 X247.284 Y138.564
G1 X247.417 Y138.431
G1 X252.583 Y133.266 E.22446
G1 X252.716 Y133.132
G1 X252.716 Y132.599
G1 X252.583 Y132.732
G1 X247.417 Y137.898 E.22446
G1 X247.284 Y138.031
G1 X247.284 Y137.498
G1 X247.417 Y137.364
G1 X252.583 Y132.199 E.22446
M73 P86 R3
G1 X252.716 Y132.065
G1 X252.716 Y131.532
G1 X252.583 Y131.666
G1 X247.417 Y136.831 E.22446
G1 X247.284 Y136.965
G1 X247.284 Y136.431
G1 X247.417 Y136.298
G1 X252.583 Y131.132 E.22446
G1 X252.716 Y130.999
G1 X252.716 Y130.466
G1 X252.583 Y130.599
G1 X247.417 Y135.764 E.22446
G1 X247.284 Y135.898
G1 X247.284 Y135.365
G1 X247.417 Y135.231
G1 X252.583 Y130.066 E.22446
G1 X252.716 Y129.932
G1 X252.716 Y129.399
G1 X252.583 Y129.533
G1 X247.417 Y134.698 E.22446
G1 X247.284 Y134.832
G1 X247.284 Y134.298
G1 X247.417 Y134.165
G1 X252.583 Y128.999 E.22446
G1 X252.716 Y128.866
G1 X252.716 Y128.333
G1 X252.583 Y128.466
G1 X247.417 Y133.631 E.22446
G1 X247.284 Y133.765
G1 X247.284 Y133.232
G1 X247.417 Y133.098
G1 X252.583 Y127.933 E.22445
G1 X252.716 Y127.799
G1 X252.716 Y127.266
G1 X252.583 Y127.4
G1 X247.417 Y132.565 E.22446
G1 X247.284 Y132.699
G1 X247.284 Y132.165
G1 X247.417 Y132.032
G1 X252.583 Y126.866 E.22446
G1 X252.716 Y126.733
G1 X252.716 Y126.2
G1 X252.583 Y126.333
G1 X247.417 Y131.498 E.22445
G1 X247.284 Y131.632
G1 X247.284 Y131.099
G1 X247.417 Y130.965
G1 X252.583 Y125.8 E.22445
G1 X252.716 Y125.666
G1 X252.716 Y125.133
G1 X252.583 Y125.267
G1 X247.417 Y130.432 E.22446
G1 X247.284 Y130.566
G1 X247.284 Y130.032
G1 X247.417 Y129.899
G1 X252.583 Y124.733 E.22446
G1 X252.716 Y124.6
M73 P86 R2
G1 X252.716 Y124.067
G1 X252.583 Y124.2
G1 X247.417 Y129.365 E.22445
G1 X247.284 Y129.499
G1 X247.284 Y128.966
G1 X247.417 Y128.832
G1 X252.583 Y123.667 E.22445
G1 X252.716 Y123.533
G1 X252.716 Y123
G1 X252.583 Y123.134
G1 X247.417 Y128.299 E.22446
G1 X247.284 Y128.433
G1 X247.284 Y127.899
G1 X247.417 Y127.766
G1 X252.583 Y122.6 E.22446
G1 X252.716 Y122.467
G1 X252.716 Y121.933
G1 X252.583 Y122.067
G1 X247.417 Y127.232 E.22445
G1 X247.284 Y127.366
G1 X247.284 Y126.833
G1 X247.417 Y126.699
G1 X252.583 Y121.534 E.22445
G1 X252.716 Y121.4
G1 X252.716 Y120.867
G1 X252.583 Y121.001
G1 X247.417 Y126.166 E.22446
G1 X247.284 Y126.299
G1 X247.284 Y125.766
G1 X247.417 Y125.633
G1 X252.583 Y120.467 E.22446
G1 X252.716 Y120.334
G1 X252.716 Y119.8
G1 X252.583 Y119.934
G1 X247.417 Y125.099 E.22445
G1 X247.284 Y125.233
G1 X247.284 Y124.7
G1 X247.417 Y124.566
G1 X252.583 Y119.401 E.22445
G1 X252.716 Y119.267
G1 X252.716 Y118.734
G1 X252.583 Y118.868
G1 X247.417 Y124.033 E.22446
G1 X247.284 Y124.166
G1 X247.284 Y123.633
G1 X247.417 Y123.5
G1 X252.583 Y118.334 E.22446
G1 X252.716 Y118.201
G1 X252.716 Y117.667
G1 X252.583 Y117.801
G1 X247.417 Y122.966 E.22445
G1 X247.284 Y123.1
G1 X247.284 Y122.567
G1 X247.417 Y122.433
G1 X252.583 Y117.268 E.22445
G1 X252.716 Y117.134
G1 X252.716 Y116.601
G1 X252.583 Y116.735
G1 X247.417 Y121.9 E.22446
G1 X247.284 Y122.033
G1 X247.284 Y121.5
G1 X247.417 Y121.367
G1 X252.583 Y116.201 E.22446
G1 X252.716 Y116.068
G1 X252.716 Y115.534
G1 X252.583 Y115.668
G1 X247.417 Y120.833 E.22445
G1 X247.284 Y120.967
G1 X247.284 Y120.434
G1 X247.417 Y120.3
G1 X252.583 Y115.135 E.22445
G1 X252.716 Y115.001
G1 X252.716 Y114.468
G1 X252.583 Y114.602
G1 X247.417 Y119.767 E.22446
G1 X247.284 Y119.9
G1 X247.284 Y119.367
G1 X247.417 Y119.234
G1 X252.583 Y114.068 E.22446
G1 X252.716 Y113.935
G1 X252.716 Y113.401
G1 X252.583 Y113.535
G1 X247.417 Y118.7 E.22445
G1 X247.284 Y118.834
G1 X247.284 Y118.301
G1 X247.417 Y118.167
G1 X252.583 Y113.002 E.22445
G1 X252.716 Y112.868
G1 X252.716 Y112.335
G1 X252.583 Y112.468
G1 X247.417 Y117.634 E.22446
G1 X247.284 Y117.767
G1 X247.284 Y117.234
G1 X247.417 Y117.1
G1 X252.583 Y111.935 E.22446
G1 X252.716 Y111.802
G1 X252.716 Y111.268
G1 X252.583 Y111.402
G1 X247.417 Y116.567 E.22445
G1 X247.284 Y116.701
G1 X247.284 Y116.168
G1 X247.417 Y116.034
G1 X252.583 Y110.869 E.22445
G1 X252.716 Y110.735
G1 X252.716 Y110.202
G1 X252.583 Y110.335
G1 X247.417 Y115.501 E.22446
G1 X247.284 Y115.634
G1 X247.284 Y115.101
G1 X247.417 Y114.967
G1 X252.583 Y109.802 E.22446
G1 X252.716 Y109.669
G1 X252.716 Y109.135
G1 X252.583 Y109.269
G1 X247.417 Y114.434 E.22445
G1 X247.284 Y114.568
G1 X247.284 Y114.035
G1 X247.417 Y113.901
G1 X252.583 Y108.736 E.22445
G1 X252.716 Y108.602
G1 X252.716 Y108.069
G1 X252.583 Y108.202
G1 X247.417 Y113.368 E.22446
G1 X247.284 Y113.501
G1 X247.284 Y112.968
G1 X247.417 Y112.834
G1 X252.583 Y107.669 E.22446
G1 X252.716 Y107.536
G1 X252.716 Y107.002
G1 X252.583 Y107.136
G1 X247.417 Y112.301 E.22445
G1 X247.284 Y112.435
G1 X247.284 Y111.902
G1 X247.417 Y111.768
G1 X252.583 Y106.603 E.22446
G1 X252.716 Y106.469
G1 X252.716 Y105.936
G1 X252.583 Y106.069
G1 X247.417 Y111.235 E.22446
G1 X247.284 Y111.368
G1 X247.284 Y110.835
G1 X247.417 Y110.701
G1 X252.583 Y105.536 E.22446
G1 X252.716 Y105.402
G1 X252.716 Y104.869
G1 X252.583 Y105.003
G1 X247.417 Y110.168 E.22446
G1 X247.284 Y110.302
G1 X247.284 Y109.769
G1 X247.417 Y109.635
G1 X252.583 Y104.47 E.22446
G1 X252.716 Y104.336
G1 X252.716 Y103.803
G1 X252.583 Y103.936
G1 X247.417 Y109.102 E.22446
G1 X247.284 Y109.235
G1 X247.284 Y108.702
G1 X247.417 Y108.568
G1 X252.583 Y103.403 E.22446
G1 X252.716 Y103.269
G1 X252.716 Y102.736
G1 X252.583 Y102.87
G1 X247.417 Y108.035 E.22446
G1 X247.284 Y108.169
G1 X247.284 Y107.635
G1 X247.417 Y107.502
G1 X252.583 Y102.337 E.22446
G1 X252.716 Y102.203
G1 X252.716 Y101.67
G1 X252.583 Y101.803
G1 X247.417 Y106.969 E.22446
G1 X247.284 Y107.102
G1 X247.284 Y106.569
G1 X247.417 Y106.435
G1 X252.583 Y101.27 E.22446
G1 X252.716 Y101.136
G1 X252.716 Y100.603
G1 X252.583 Y100.737
G1 X247.417 Y105.902 E.22446
G1 X247.284 Y106.036
G1 X247.284 Y105.502
G1 X247.417 Y105.369
G1 X252.583 Y100.204 E.22446
G1 X252.716 Y100.07
G1 X252.716 Y99.537
G1 X252.583 Y99.67
G1 X247.417 Y104.836 E.22446
G1 X247.284 Y104.969
G1 X247.284 Y104.436
G1 X247.417 Y104.302
G1 X252.583 Y99.137 E.22446
G1 X252.716 Y99.003
G1 X252.716 Y98.47
G1 X252.583 Y98.604
G1 X247.417 Y103.769 E.22446
G1 X247.284 Y103.903
G1 X247.284 Y103.369
G1 X247.417 Y103.236
G1 X252.583 Y98.071 E.22446
G1 X252.716 Y97.937
G1 X252.716 Y97.404
G1 X252.583 Y97.537
G1 X247.417 Y102.703 E.22446
G1 X247.284 Y102.836
G1 X247.284 Y102.303
G1 X247.417 Y102.169
G1 X252.583 Y97.004 E.22446
G1 X252.716 Y96.87
G1 X252.716 Y96.337
G1 X252.583 Y96.471
G1 X247.417 Y101.636 E.22446
G1 X247.284 Y101.77
G1 X247.284 Y101.236
G1 X247.417 Y101.103
G1 X252.583 Y95.938 E.22446
G1 X252.716 Y95.804
G1 X252.716 Y95.271
G1 X252.583 Y95.404
G1 X247.417 Y100.569 E.22446
G1 X247.284 Y100.703
G1 X247.284 Y100.17
G1 X247.417 Y100.036
G1 X252.583 Y94.871 E.22446
G1 X252.716 Y94.737
G1 X252.716 Y94.204
G1 X252.583 Y94.338
G1 X247.417 Y99.503 E.22446
G1 X247.284 Y99.637
G1 X247.284 Y99.103
G1 X247.417 Y98.97
G1 X252.583 Y93.804 E.22446
G1 X252.716 Y93.671
G1 X252.716 Y93.138
G1 X252.583 Y93.271
G1 X247.417 Y98.436 E.22446
G1 X247.284 Y98.57
G1 X247.284 Y98.037
G1 X247.417 Y97.903
G1 X252.583 Y92.738 E.22446
G1 X252.716 Y92.604
G1 X252.716 Y92.071
G1 X252.583 Y92.205
G1 X247.417 Y97.37 E.22446
G1 X247.284 Y97.504
G1 X247.284 Y96.97
G1 X247.417 Y96.837
G1 X252.583 Y91.671 E.22446
G1 X252.716 Y91.538
G1 X252.716 Y91.005
G1 X252.583 Y91.138
G1 X247.417 Y96.303 E.22446
G1 X247.284 Y96.437
G1 X247.284 Y95.904
G1 X247.417 Y95.77
G1 X252.583 Y90.605 E.22446
G1 X252.716 Y90.471
G1 X252.716 Y89.938
G1 X252.583 Y90.072
G1 X247.417 Y95.237 E.22446
G1 X247.284 Y95.371
G1 X247.284 Y94.837
G1 X247.417 Y94.704
G1 X252.583 Y89.538 E.22446
G1 X252.716 Y89.405
G1 X252.716 Y88.872
G1 X252.583 Y89.005
G1 X247.417 Y94.17 E.22446
G1 X247.284 Y94.304
G1 X247.284 Y93.771
G1 X247.417 Y93.637
G1 X252.583 Y88.472 E.22446
G1 X252.716 Y88.338
G1 X252.716 Y87.805
G1 X252.583 Y87.939
G1 X247.417 Y93.104 E.22446
G1 X247.284 Y93.238
G1 X247.284 Y92.704
G1 X247.417 Y92.571
G1 X252.583 Y87.405 E.22445
G1 X252.716 Y87.272
G1 X252.716 Y86.738
G1 X252.583 Y86.872
G1 X247.417 Y92.037 E.22445
G1 X247.284 Y92.171
G1 X247.284 Y91.638
G1 X247.417 Y91.504
G1 X252.583 Y86.339 E.22445
G1 X252.716 Y86.205
G1 X252.716 Y85.672
G1 X252.583 Y85.806
G1 X247.417 Y90.971 E.22446
G1 X247.284 Y91.105
G1 X247.284 Y90.571
G1 X247.417 Y90.438
G1 X252.583 Y85.272 E.22445
G1 X252.716 Y85.139
G1 X252.716 Y84.605
G1 X252.583 Y84.739
G1 X247.417 Y89.904 E.22445
G1 X247.284 Y90.038
G1 X247.284 Y89.505
G1 X247.417 Y89.371
G1 X252.583 Y84.206 E.22445
G1 X252.716 Y84.072
G1 X252.716 Y83.539
G1 X252.583 Y83.673
G1 X247.417 Y88.838 E.22446
G1 X247.284 Y88.971
G1 X247.284 Y88.438
G1 X247.417 Y88.305
G1 X252.583 Y83.139 E.22445
G1 X252.716 Y83.006
G1 X252.716 Y82.472
G1 X252.583 Y82.606
G1 X247.417 Y87.771 E.22445
G1 X247.284 Y87.905
G1 X247.284 Y87.372
G1 X247.417 Y87.238
G1 X252.583 Y82.073 E.22445
G1 X252.716 Y81.939
G1 X252.716 Y81.406
G1 X252.583 Y81.54
G1 X247.417 Y86.705 E.22446
G1 X247.284 Y86.838
G1 X247.284 Y86.305
G1 X247.417 Y86.172
G1 X252.583 Y81.006 E.22445
G1 X252.716 Y80.873
G1 X252.716 Y80.339
G1 X252.583 Y80.473
G1 X247.417 Y85.638 E.22445
G1 X247.284 Y85.772
G1 X247.284 Y85.239
G1 X247.417 Y85.105
G1 X252.583 Y79.94 E.22445
G1 X252.716 Y79.806
G1 X252.716 Y79.273
G1 X252.583 Y79.407
G1 X247.417 Y84.572 E.22446
G1 X247.284 Y84.705
G1 X247.284 Y84.172
G1 X247.417 Y84.039
G1 X252.583 Y78.873 E.22445
G1 X252.716 Y78.74
G1 X252.716 Y78.206
G1 X252.583 Y78.34
G1 X247.417 Y83.505 E.22445
G1 X247.284 Y83.639
G1 X247.284 Y83.106
G1 X247.417 Y82.972
G1 X252.583 Y77.807 E.22445
G1 X252.716 Y77.673
G1 X252.716 Y77.14
G1 X252.583 Y77.273
G1 X247.417 Y82.439 E.22446
G1 X247.284 Y82.572
G1 X247.284 Y82.039
G1 X247.417 Y81.905
G1 X252.583 Y76.74 E.22445
G1 X252.716 Y76.607
G1 X252.716 Y76.073
G1 X252.583 Y76.207
G1 X247.417 Y81.372 E.22445
G1 X247.284 Y81.506
G1 X247.284 Y80.973
G1 X247.417 Y80.839
G1 X252.583 Y75.674 E.22445
G1 X252.716 Y75.54
G1 X252.716 Y75.007
G1 X252.583 Y75.14
G1 X247.417 Y80.306 E.22446
G1 X247.284 Y80.439
G1 X247.284 Y79.906
G1 X247.417 Y79.772
G1 X252.583 Y74.607 E.22446
G1 X252.716 Y74.474
G1 X252.716 Y73.94
G1 X252.583 Y74.074
G1 X247.417 Y79.239 E.22446
G1 X247.284 Y79.373
G1 X247.284 Y78.84
G1 X247.417 Y78.706
G1 X252.583 Y73.541 E.22446
G1 X252.716 Y73.407
G1 X252.716 Y72.874
G1 X252.583 Y73.007
G1 X247.417 Y78.173 E.22446
G1 X247.284 Y78.306
G1 X247.284 Y77.773
G1 X247.417 Y77.639
G1 X252.583 Y72.474 E.22446
G1 X252.716 Y72.341
G1 X252.716 Y71.807
G1 X252.583 Y71.941
G1 X247.417 Y77.106 E.22446
G1 X247.284 Y77.24
M73 P87 R2
G1 X247.284 Y76.707
G1 X247.417 Y76.573
G1 X252.583 Y71.408 E.22446
G1 X252.716 Y71.274
G1 X252.716 Y70.741
G1 X252.583 Y70.874
G1 X247.417 Y76.04 E.22446
G1 X247.284 Y76.173
G1 X247.284 Y75.64
G1 X247.417 Y75.506
G1 X252.583 Y70.341 E.22446
G1 X252.716 Y70.208
G1 X252.716 Y69.674
G1 X252.583 Y69.808
G1 X247.417 Y74.973 E.22446
G1 X247.284 Y75.107
G1 X247.284 Y74.574
G1 X247.417 Y74.44
G1 X252.583 Y69.275 E.22446
G1 X252.716 Y69.141
G1 X252.716 Y68.608
G1 X252.583 Y68.741
G1 X247.417 Y73.907 E.22446
G1 X247.284 Y74.04
G1 X247.284 Y73.507
G1 X247.417 Y73.373
G1 X252.583 Y68.208 E.22446
G1 X252.716 Y68.074
G1 X252.716 Y67.541
G1 X252.583 Y67.675
G1 X247.417 Y72.84 E.22446
G1 X247.284 Y72.974
G1 X247.284 Y72.44
G1 X247.417 Y72.307
G1 X252.583 Y67.142 E.22446
G1 X252.716 Y67.008
G1 X252.716 Y66.475
G1 X252.583 Y66.608
G1 X247.417 Y71.774 E.22446
G1 X247.284 Y71.907
G1 X247.284 Y71.374
G1 X247.417 Y71.24
G1 X252.583 Y66.075 E.22446
G1 X252.716 Y65.941
G1 X252.716 Y65.408
G1 X252.583 Y65.542
G1 X247.417 Y70.707 E.22446
G1 X247.284 Y70.841
G1 X247.284 Y70.307
G1 X247.417 Y70.174
G1 X252.583 Y65.009 E.22446
G1 X252.716 Y64.875
G1 X252.716 Y64.342
G1 X252.583 Y64.475
G1 X247.417 Y69.641 E.22446
G1 X247.284 Y69.774
G1 X247.284 Y69.241
G1 X247.417 Y69.107
G1 X252.583 Y63.942 E.22446
G1 X252.716 Y63.808
G1 X252.716 Y63.275
G1 X252.583 Y63.409
G1 X247.417 Y68.574 E.22446
G1 X247.284 Y68.708
G1 X247.284 Y68.174
G1 X247.417 Y68.041
G1 X252.583 Y62.876 E.22446
G1 X252.716 Y62.742
G1 X252.716 Y62.209
G1 X252.583 Y62.342
G1 X247.417 Y67.508 E.22446
G1 X247.284 Y67.641
G1 X247.284 Y67.108
G1 X247.417 Y66.974
G1 X252.583 Y61.809 E.22446
G1 X252.716 Y61.675
G1 X252.716 Y61.142
G1 X252.583 Y61.276
G1 X247.417 Y66.441 E.22446
G1 X247.284 Y66.575
G1 X247.284 Y66.041
G1 X247.417 Y65.908
G1 X252.583 Y60.743 E.22446
G1 X252.716 Y60.609
G1 X252.716 Y60.076
G1 X252.583 Y60.209
G1 X247.417 Y65.375 E.22446
G1 X247.284 Y65.508
G1 X247.284 Y64.975
G1 X247.417 Y64.841
G1 X252.583 Y59.676 E.22446
G1 X252.716 Y59.542
G1 X252.716 Y59.009
G1 X252.583 Y59.143
G1 X247.417 Y64.308 E.22446
G1 X247.284 Y64.442
G1 X247.284 Y63.908
G1 X247.417 Y63.775
G1 X252.583 Y58.609 E.22446
G1 X252.716 Y58.476
G1 X252.716 Y57.943
G1 X252.583 Y58.076
G1 X247.417 Y63.241 E.22446
G1 X247.284 Y63.375
G1 X247.284 Y62.842
G1 X247.417 Y62.708
G1 X252.583 Y57.543 E.22446
G1 X252.716 Y57.409
G1 X252.716 Y56.876
G1 X252.583 Y57.01
G1 X247.417 Y62.175 E.22446
G1 X247.284 Y62.309
G1 X247.284 Y61.775
G1 X247.417 Y61.642
G1 X252.583 Y56.476 E.22446
G1 X252.716 Y56.343
G1 X252.716 Y55.81
G1 X252.583 Y55.943
G1 X247.417 Y61.108 E.22446
G1 X247.284 Y61.242
G1 X247.284 Y60.709
G1 X247.417 Y60.575
G1 X252.583 Y55.41 E.22446
G1 X252.716 Y55.276
G1 X252.716 Y54.743
G1 X252.583 Y54.877
G1 X247.417 Y60.042 E.22446
G1 X247.284 Y60.176
G1 X247.284 Y59.642
G1 X247.417 Y59.509
G1 X252.583 Y54.343 E.22446
G1 X252.716 Y54.21
G1 X252.716 Y53.677
G1 X252.583 Y53.81
G1 X247.417 Y58.975 E.22446
G1 X247.284 Y59.109
G1 X247.284 Y58.576
G1 X247.417 Y58.442
G1 X252.583 Y53.277 E.22446
G1 X252.716 Y53.143
G1 X252.716 Y52.61
G1 X252.583 Y52.744
G1 X247.417 Y57.909 E.22446
G1 X247.284 Y58.043
G1 X247.284 Y57.509
G1 X247.417 Y57.376
G1 X252.583 Y52.21 E.22446
G1 X252.716 Y52.077
G1 X252.716 Y51.543
G1 X252.583 Y51.677
G1 X247.417 Y56.842 E.22446
G1 X247.284 Y56.976
G1 X247.284 Y56.443
G1 X247.417 Y56.309
G1 X252.583 Y51.144 E.22446
G1 X252.716 Y51.01
G1 X252.716 Y50.477
G1 X252.583 Y50.611
G1 X247.417 Y55.776 E.22446
G1 X247.284 Y55.91
G1 X247.284 Y55.376
G1 X247.417 Y55.243
G1 X252.583 Y50.077 E.22446
G1 X252.716 Y49.944
G1 X252.716 Y49.41
G1 X252.583 Y49.544
G1 X247.417 Y54.709 E.22446
G1 X247.284 Y54.843
G1 X247.284 Y54.31
G1 X247.417 Y54.176
G1 X252.583 Y49.011 E.22446
G1 X252.716 Y48.877
G1 X252.716 Y48.344
G1 X252.583 Y48.478
G1 X247.417 Y53.643 E.22446
G1 X247.284 Y53.776
G1 X247.284 Y53.243
G1 X247.417 Y53.11
G1 X252.583 Y47.944 E.22445
G1 X252.716 Y47.811
G1 X252.716 Y47.277
G1 X252.583 Y47.411
G1 X247.417 Y52.576 E.22445
G1 X247.284 Y52.71
G1 X247.284 Y52.177
G1 X247.417 Y52.043
G1 X252.583 Y46.878 E.22446
G1 X252.716 Y46.744
G1 X252.716 Y46.211
G1 X252.583 Y46.345
G1 X247.417 Y51.51 E.22446
G1 X247.284 Y51.643
G1 X247.284 Y51.11
G1 X247.417 Y50.977
G1 X252.583 Y45.811 E.22445
G1 X252.716 Y45.678
G1 X252.716 Y45.144
G1 X252.583 Y45.278
G1 X247.417 Y50.443 E.22445
G1 X247.284 Y50.577
G1 X247.284 Y50.044
G1 X247.417 Y49.91
G1 X252.583 Y44.745 E.22446
G1 X252.716 Y44.611
G1 X252.716 Y44.078
G1 X252.583 Y44.212
G1 X247.417 Y49.377 E.22446
G1 X247.284 Y49.51
G1 X247.284 Y48.977
G1 X247.417 Y48.844
G1 X252.583 Y43.678 E.22446
G1 X252.716 Y43.545
G1 X252.716 Y43.011
G1 X252.583 Y43.145
G1 X247.417 Y48.31 E.22446
G1 X247.284 Y48.444
G1 X247.284 Y47.911
G1 X247.417 Y47.777
G1 X252.583 Y42.612 E.22446
G1 X252.716 Y42.478
G1 X252.716 Y41.945
G1 X252.583 Y42.079
G1 X247.417 Y47.244 E.22446
G1 X247.284 Y47.377
G1 X247.284 Y46.844
G1 X247.417 Y46.711
G1 X252.583 Y41.545 E.22446
G1 X252.716 Y41.412
G1 X252.716 Y40.878
G1 X252.583 Y41.012
G1 X247.417 Y46.177 E.22446
G1 X247.284 Y46.311
G1 X247.284 Y45.778
G1 X247.417 Y45.644
G1 X252.583 Y40.479 E.22446
G1 X252.716 Y40.345
G1 X252.716 Y39.812
G1 X252.583 Y39.945
G1 X247.417 Y45.111 E.22446
G1 X247.284 Y45.244
G1 X247.284 Y44.711
G1 X247.417 Y44.577
G1 X252.583 Y39.412 E.22446
G1 X252.716 Y39.279
G1 X252.716 Y38.745
G1 X252.583 Y38.879
G1 X247.417 Y44.044 E.22446
G1 X247.284 Y44.178
G1 X247.284 Y43.645
G1 X247.417 Y43.511
G1 X252.583 Y38.346 E.22446
G1 X252.716 Y38.212
G1 X252.716 Y37.679
G1 X252.583 Y37.812
G1 X247.417 Y42.978 E.22446
G1 X247.284 Y43.111
G1 X247.284 Y42.578
G1 X247.417 Y42.444
G1 X252.583 Y37.279 E.22446
G1 X252.716 Y37.146
G1 X252.716 Y36.612
G1 X252.583 Y36.746
G1 X247.417 Y41.911 E.22446
G1 X247.284 Y42.045
G1 X247.284 Y41.512
G1 X247.417 Y41.378
G1 X252.583 Y36.213 E.22446
G1 X252.716 Y36.079
G1 X252.716 Y35.546
G1 X252.583 Y35.679
G1 X247.417 Y40.845 E.22446
G1 X247.284 Y40.978
G1 X247.284 Y40.445
G1 X247.417 Y40.311
G1 X252.583 Y35.146 E.22446
G1 X252.716 Y35.013
G1 X252.716 Y34.479
G1 X252.583 Y34.613
G1 X247.417 Y39.778 E.22446
G1 X247.284 Y39.912
G1 X247.284 Y39.379
G1 X247.417 Y39.245
G1 X252.583 Y34.08 E.22446
G1 X252.716 Y33.946
G1 X252.716 Y33.413
G1 X252.583 Y33.546
G1 X247.417 Y38.712 E.22446
G1 X247.284 Y38.845
G1 X247.284 Y38.312
G1 X247.417 Y38.178
G1 X252.583 Y33.013 E.22446
G1 X252.716 Y32.879
G1 X252.716 Y32.346
G1 X252.583 Y32.48
G1 X247.417 Y37.645 E.22446
G1 X247.284 Y37.779
G1 X247.284 Y37.246
G1 X247.417 Y37.112
G1 X252.583 Y31.947 E.22446
G1 X252.716 Y31.813
G1 X252.716 Y31.28
G1 X252.583 Y31.413
G1 X247.417 Y36.579 E.22446
G1 X247.284 Y36.712
G1 X247.284 Y36.179
G1 X247.417 Y36.045
G1 X252.583 Y30.88 E.22446
G1 X252.716 Y30.746
G1 X252.716 Y30.213
G1 X252.583 Y30.347
G1 X247.417 Y35.512 E.22446
G1 X247.284 Y35.646
G1 X247.284 Y35.112
G1 X247.417 Y34.979
G1 X252.583 Y29.814 E.22446
G1 X252.716 Y29.68
G1 X252.716 Y29.147
G1 X252.583 Y29.28
G1 X247.417 Y34.446 E.22446
G1 X247.284 Y34.579
G1 X247.284 Y34.046
G1 X247.417 Y33.912
G1 X252.583 Y28.747 E.22446
G1 X252.716 Y28.613
G1 X252.513 Y28.284
G1 X252.379 Y28.417
G1 X247.214 Y33.583 E.22446
G1 X247.08 Y33.716
G1 X246.547 Y33.716
G1 X246.681 Y33.583
G1 X251.846 Y28.417 E.22446
G1 X251.979 Y28.284
G1 X251.446 Y28.284
G1 X251.313 Y28.417
G1 X246.147 Y33.583 E.22446
G1 X246.014 Y33.716
G1 X245.48 Y33.716
G1 X245.614 Y33.583
G1 X250.779 Y28.417 E.22446
G1 X250.913 Y28.284
G1 X250.38 Y28.284
G1 X250.246 Y28.417
G1 X245.081 Y33.583 E.22446
G1 X244.947 Y33.716
G1 X244.414 Y33.716
G1 X244.548 Y33.583
G1 X249.713 Y28.417 E.22446
G1 X249.846 Y28.284
G1 X249.313 Y28.284
G1 X249.18 Y28.417
G1 X244.014 Y33.583 E.22446
G1 X243.881 Y33.716
G1 X243.347 Y33.716
G1 X243.481 Y33.583
G1 X248.646 Y28.417 E.22446
G1 X248.78 Y28.284
G1 X248.247 Y28.284
G1 X248.113 Y28.417
G1 X242.948 Y33.583 E.22446
G1 X242.814 Y33.716
G1 X242.281 Y33.716
G1 X242.415 Y33.583
G1 X247.58 Y28.417 E.22446
G1 X247.713 Y28.284
G1 X247.18 Y28.284
G1 X247.047 Y28.417
G1 X241.881 Y33.583 E.22446
G1 X241.748 Y33.716
G1 X241.214 Y33.716
G1 X241.348 Y33.583
G1 X246.513 Y28.417 E.22446
G1 X246.647 Y28.284
G1 X246.114 Y28.284
G1 X245.98 Y28.417
G1 X240.815 Y33.583 E.22446
G1 X240.681 Y33.716
G1 X240.148 Y33.716
G1 X240.281 Y33.583
G1 X245.447 Y28.417 E.22446
G1 X245.58 Y28.284
G1 X245.047 Y28.284
G1 X244.913 Y28.417
G1 X239.748 Y33.583 E.22446
G1 X239.615 Y33.716
G1 X239.081 Y33.716
G1 X239.215 Y33.583
G1 X244.38 Y28.417 E.22446
G1 X244.514 Y28.284
G1 X243.981 Y28.284
G1 X243.847 Y28.417
G1 X238.682 Y33.583 E.22446
G1 X238.548 Y33.716
G1 X238.015 Y33.716
G1 X238.148 Y33.583
G1 X243.314 Y28.417 E.22446
G1 X243.447 Y28.284
G1 X242.914 Y28.284
G1 X242.78 Y28.417
G1 X237.615 Y33.583 E.22446
G1 X237.482 Y33.716
G1 X236.948 Y33.716
G1 X237.082 Y33.583
G1 X242.247 Y28.417 E.22446
G1 X242.381 Y28.284
G1 X241.848 Y28.284
G1 X241.714 Y28.417
G1 X236.549 Y33.583 E.22446
G1 X236.415 Y33.716
G1 X235.882 Y33.716
G1 X236.015 Y33.583
G1 X241.181 Y28.417 E.22446
G1 X241.314 Y28.284
G1 X240.781 Y28.284
G1 X240.647 Y28.417
G1 X235.482 Y33.583 E.22446
G1 X235.349 Y33.716
G1 X234.815 Y33.716
G1 X234.949 Y33.583
G1 X240.114 Y28.417 E.22446
G1 X240.248 Y28.284
G1 X239.715 Y28.284
G1 X239.581 Y28.417
G1 X234.416 Y33.583 E.22446
G1 X234.282 Y33.716
G1 X233.749 Y33.716
G1 X233.882 Y33.583
G1 X239.048 Y28.417 E.22446
G1 X239.181 Y28.284
G1 X238.648 Y28.284
G1 X238.514 Y28.417
G1 X233.349 Y33.583 E.22446
G1 X233.215 Y33.716
G1 X232.682 Y33.716
G1 X232.816 Y33.583
G1 X237.981 Y28.417 E.22446
G1 X238.115 Y28.284
G1 X237.582 Y28.284
G1 X237.448 Y28.417
G1 X232.283 Y33.583 E.22446
G1 X232.149 Y33.716
G1 X231.616 Y33.716
G1 X231.749 Y33.583
G1 X236.915 Y28.417 E.22446
G1 X237.048 Y28.284
G1 X236.515 Y28.284
G1 X236.381 Y28.417
G1 X231.216 Y33.583 E.22446
G1 X231.082 Y33.716
G1 X230.549 Y33.716
G1 X230.683 Y33.583
G1 X235.848 Y28.417 E.22446
G1 X235.982 Y28.284
M73 P88 R2
G1 X235.448 Y28.284
G1 X235.315 Y28.417
G1 X230.15 Y33.583 E.22446
G1 X230.016 Y33.716
G1 X229.483 Y33.716
G1 X229.616 Y33.583
G1 X234.782 Y28.417 E.22446
G1 X234.915 Y28.284
G1 X234.382 Y28.284
G1 X234.248 Y28.417
G1 X229.083 Y33.583 E.22446
G1 X228.949 Y33.716
G1 X228.416 Y33.716
G1 X228.55 Y33.583
G1 X233.715 Y28.417 E.22445
G1 X233.849 Y28.284
G1 X233.315 Y28.284
G1 X233.182 Y28.417
G1 X228.017 Y33.583 E.22445
G1 X227.883 Y33.716
G1 X227.35 Y33.716
G1 X227.483 Y33.583
G1 X232.649 Y28.417 E.22446
G1 X232.782 Y28.284
G1 X232.249 Y28.284
G1 X232.115 Y28.417
G1 X226.95 Y33.583 E.22446
G1 X226.816 Y33.716
G1 X226.283 Y33.716
G1 X226.417 Y33.583
G1 X231.582 Y28.417 E.22446
G1 X231.716 Y28.284
G1 X231.182 Y28.284
G1 X231.049 Y28.417
G1 X225.884 Y33.583 E.22446
G1 X225.75 Y33.716
G1 X225.217 Y33.716
G1 X225.35 Y33.583
G1 X230.516 Y28.417 E.22446
G1 X230.649 Y28.284
G1 X230.116 Y28.284
G1 X229.982 Y28.417
G1 X224.817 Y33.583 E.22446
G1 X224.683 Y33.716
G1 X224.15 Y33.716
G1 X224.284 Y33.583
G1 X229.449 Y28.417 E.22446
G1 X229.583 Y28.284
G1 X229.049 Y28.284
G1 X228.916 Y28.417
G1 X223.75 Y33.583 E.22446
G1 X223.617 Y33.716
G1 X223.084 Y33.716
G1 X223.217 Y33.583
G1 X228.382 Y28.417 E.22446
G1 X228.516 Y28.284
G1 X227.983 Y28.284
G1 X227.849 Y28.417
G1 X222.684 Y33.583 E.22446
G1 X222.55 Y33.716
G1 X222.017 Y33.716
G1 X222.151 Y33.583
G1 X227.316 Y28.417 E.22446
G1 X227.45 Y28.284
G1 X226.916 Y28.284
G1 X226.783 Y28.417
G1 X221.617 Y33.583 E.22446
G1 X221.484 Y33.716
G1 X220.951 Y33.716
G1 X221.084 Y33.583
G1 X226.249 Y28.417 E.22446
G1 X226.383 Y28.284
G1 X225.85 Y28.284
G1 X225.716 Y28.417
G1 X220.551 Y33.583 E.22446
G1 X220.417 Y33.716
G1 X219.884 Y33.716
G1 X220.018 Y33.583
G1 X225.183 Y28.417 E.22446
G1 X225.317 Y28.284
G1 X224.783 Y28.284
G1 X224.65 Y28.417
G1 X219.484 Y33.583 E.22446
G1 X219.351 Y33.716
G1 X218.818 Y33.716
G1 X218.951 Y33.583
G1 X224.116 Y28.417 E.22446
G1 X224.25 Y28.284
G1 X223.717 Y28.284
G1 X223.583 Y28.417
G1 X218.418 Y33.583 E.22446
G1 X218.284 Y33.716
G1 X217.751 Y33.716
G1 X217.885 Y33.583
G1 X223.05 Y28.417 E.22446
G1 X223.184 Y28.284
G1 X222.65 Y28.284
G1 X222.517 Y28.417
G1 X217.351 Y33.583 E.22446
G1 X217.218 Y33.716
G1 X216.684 Y33.716
G1 X216.818 Y33.583
G1 X221.983 Y28.417 E.22446
G1 X222.117 Y28.284
G1 X221.584 Y28.284
G1 X221.45 Y28.417
G1 X216.285 Y33.583 E.22446
G1 X216.151 Y33.716
G1 X215.618 Y33.716
G1 X215.752 Y33.583
G1 X220.917 Y28.417 E.22446
G1 X221.051 Y28.284
G1 X220.517 Y28.284
G1 X220.384 Y28.417
G1 X215.218 Y33.583 E.22446
G1 X215.085 Y33.716
G1 X214.551 Y33.716
G1 X214.685 Y33.583
G1 X219.85 Y28.417 E.22446
G1 X219.984 Y28.284
G1 X219.451 Y28.284
G1 X219.317 Y28.417
G1 X214.152 Y33.583 E.22446
G1 X214.018 Y33.716
G1 X213.485 Y33.716
G1 X213.619 Y33.583
G1 X218.784 Y28.417 E.22446
G1 X218.917 Y28.284
G1 X218.384 Y28.284
G1 X218.251 Y28.417
G1 X213.085 Y33.583 E.22446
G1 X212.952 Y33.716
G1 X212.418 Y33.716
G1 X212.552 Y33.583
G1 X217.717 Y28.417 E.22446
G1 X217.851 Y28.284
G1 X217.318 Y28.284
G1 X217.184 Y28.417
G1 X212.019 Y33.583 E.22446
G1 X211.885 Y33.716
G1 X211.352 Y33.716
G1 X211.486 Y33.583
G1 X216.651 Y28.417 E.22446
G1 X216.784 Y28.284
G1 X216.251 Y28.284
G1 X216.118 Y28.417
G1 X210.952 Y33.583 E.22446
G1 X210.819 Y33.716
G1 X210.285 Y33.716
G1 X210.419 Y33.583
G1 X215.584 Y28.417 E.22446
G1 X215.718 Y28.284
G1 X215.185 Y28.284
G1 X215.051 Y28.417
G1 X209.886 Y33.583 E.22446
G1 X209.752 Y33.716
G1 X209.219 Y33.716
G1 X209.353 Y33.583
G1 X214.518 Y28.417 E.22446
G1 X214.651 Y28.284
G1 X214.118 Y28.284
G1 X213.985 Y28.417
G1 X208.819 Y33.583 E.22446
G1 X208.686 Y33.716
G1 X208.152 Y33.716
G1 X208.286 Y33.583
G1 X213.451 Y28.417 E.22446
G1 X213.585 Y28.284
G1 X213.052 Y28.284
G1 X212.918 Y28.417
G1 X207.753 Y33.583 E.22446
G1 X207.619 Y33.716
G1 X207.086 Y33.716
G1 X207.22 Y33.583
G1 X212.385 Y28.417 E.22446
G1 X212.518 Y28.284
G1 X211.985 Y28.284
G1 X211.851 Y28.417
G1 X206.686 Y33.583 E.22446
G1 X206.553 Y33.716
G1 X206.019 Y33.716
G1 X206.153 Y33.583
G1 X211.318 Y28.417 E.22446
G1 X211.452 Y28.284
G1 X210.919 Y28.284
G1 X210.785 Y28.417
G1 X205.62 Y33.583 E.22446
G1 X205.486 Y33.716
G1 X204.953 Y33.716
G1 X205.086 Y33.583
G1 X210.252 Y28.417 E.22446
G1 X210.385 Y28.284
G1 X209.852 Y28.284
G1 X209.718 Y28.417
G1 X204.553 Y33.583 E.22446
G1 X204.42 Y33.716
G1 X203.886 Y33.716
G1 X204.02 Y33.583
G1 X209.185 Y28.417 E.22446
G1 X209.319 Y28.284
G1 X208.786 Y28.284
G1 X208.652 Y28.417
G1 X203.487 Y33.583 E.22446
G1 X203.353 Y33.716
G1 X202.82 Y33.716
G1 X202.953 Y33.583
G1 X208.119 Y28.417 E.22446
G1 X208.252 Y28.284
G1 X207.719 Y28.284
G1 X207.585 Y28.417
G1 X202.42 Y33.583 E.22446
G1 X202.287 Y33.716
G1 X201.753 Y33.716
G1 X201.887 Y33.583
G1 X207.052 Y28.417 E.22446
G1 X207.186 Y28.284
G1 X206.653 Y28.284
G1 X206.519 Y28.417
G1 X201.354 Y33.583 E.22446
G1 X201.22 Y33.716
G1 X200.687 Y33.716
G1 X200.82 Y33.583
G1 X205.986 Y28.417 E.22446
G1 X206.119 Y28.284
G1 X205.586 Y28.284
G1 X205.452 Y28.417
G1 X200.287 Y33.583 E.22446
G1 X200.154 Y33.716
G1 X199.62 Y33.716
G1 X199.754 Y33.583
G1 X204.919 Y28.417 E.22446
G1 X205.053 Y28.284
G1 X204.52 Y28.284
G1 X204.386 Y28.417
G1 X199.221 Y33.583 E.22446
G1 X199.087 Y33.716
G1 X198.554 Y33.716
G1 X198.687 Y33.583
G1 X203.853 Y28.417 E.22446
G1 X203.986 Y28.284
G1 X203.453 Y28.284
G1 X203.319 Y28.417
G1 X198.154 Y33.583 E.22446
G1 X198.02 Y33.716
G1 X197.487 Y33.716
G1 X197.621 Y33.583
G1 X202.786 Y28.417 E.22446
G1 X202.92 Y28.284
G1 X202.387 Y28.284
G1 X202.253 Y28.417
G1 X197.088 Y33.583 E.22446
G1 X196.954 Y33.716
G1 X196.421 Y33.716
G1 X196.554 Y33.583
G1 X201.72 Y28.417 E.22446
G1 X201.853 Y28.284
G1 X201.32 Y28.284
G1 X201.186 Y28.417
G1 X196.021 Y33.583 E.22446
G1 X195.887 Y33.716
G1 X195.354 Y33.716
G1 X195.488 Y33.583
G1 X200.653 Y28.417 E.22446
G1 X200.787 Y28.284
G1 X200.253 Y28.284
G1 X200.12 Y28.417
G1 X194.955 Y33.583 E.22446
G1 X194.821 Y33.716
G1 X194.288 Y33.716
G1 X194.421 Y33.583
G1 X199.587 Y28.417 E.22446
G1 X199.72 Y28.284
G1 X199.187 Y28.284
G1 X199.053 Y28.417
G1 X193.888 Y33.583 E.22446
G1 X193.754 Y33.716
G1 X193.221 Y33.716
G1 X193.355 Y33.583
G1 X198.52 Y28.417 E.22446
G1 X198.654 Y28.284
G1 X198.12 Y28.284
G1 X197.987 Y28.417
G1 X192.822 Y33.583 E.22445
G1 X192.688 Y33.716
G1 X192.155 Y33.716
G1 X192.288 Y33.583
G1 X197.454 Y28.417 E.22445
G1 X197.587 Y28.284
G1 X197.054 Y28.284
G1 X196.92 Y28.417
G1 X191.755 Y33.583 E.22446
G1 X191.621 Y33.716
G1 X191.088 Y33.716
G1 X191.222 Y33.583
G1 X196.387 Y28.417 E.22446
G1 X196.521 Y28.284
G1 X195.987 Y28.284
G1 X195.854 Y28.417
G1 X190.689 Y33.583 E.22445
G1 X190.555 Y33.716
G1 X190.022 Y33.716
G1 X190.155 Y33.583
G1 X195.321 Y28.417 E.22445
G1 X195.454 Y28.284
G1 X194.921 Y28.284
G1 X194.787 Y28.417
G1 X189.622 Y33.583 E.22446
G1 X189.488 Y33.716
G1 X188.955 Y33.716
G1 X189.089 Y33.583
G1 X194.254 Y28.417 E.22446
G1 X194.388 Y28.284
G1 X193.854 Y28.284
G1 X193.721 Y28.417
G1 X188.555 Y33.583 E.22445
G1 X188.422 Y33.716
G1 X187.889 Y33.716
G1 X188.022 Y33.583
G1 X193.187 Y28.417 E.22445
G1 X193.321 Y28.284
G1 X192.788 Y28.284
G1 X192.654 Y28.417
G1 X187.489 Y33.583 E.22446
G1 X187.355 Y33.716
G1 X186.822 Y33.716
G1 X186.956 Y33.583
G1 X192.121 Y28.417 E.22446
G1 X192.255 Y28.284
G1 X191.721 Y28.284
G1 X191.588 Y28.417
G1 X186.422 Y33.583 E.22446
G1 X186.289 Y33.716
G1 X185.756 Y33.716
G1 X185.889 Y33.583
G1 X191.054 Y28.417 E.22446
G1 X191.188 Y28.284
G1 X190.655 Y28.284
G1 X190.521 Y28.417
G1 X185.356 Y33.583 E.22446
G1 X185.222 Y33.716
G1 X184.689 Y33.716
G1 X184.823 Y33.583
G1 X189.988 Y28.417 E.22446
G1 X190.122 Y28.284
G1 X189.588 Y28.284
G1 X189.455 Y28.417
G1 X184.289 Y33.583 E.22446
G1 X184.156 Y33.716
G1 X183.623 Y33.716
G1 X183.756 Y33.583
G1 X188.921 Y28.417 E.22446
G1 X189.055 Y28.284
G1 X188.522 Y28.284
G1 X188.388 Y28.417
G1 X183.223 Y33.583 E.22446
G1 X183.089 Y33.716
G1 X182.556 Y33.716
G1 X182.69 Y33.583
G1 X187.855 Y28.417 E.22446
G1 X187.989 Y28.284
G1 X187.455 Y28.284
G1 X187.322 Y28.417
G1 X182.156 Y33.583 E.22446
G1 X182.023 Y33.716
G1 X181.489 Y33.716
G1 X181.623 Y33.583
G1 X186.788 Y28.417 E.22446
G1 X186.922 Y28.284
G1 X186.389 Y28.284
G1 X186.255 Y28.417
G1 X181.09 Y33.583 E.22446
G1 X180.956 Y33.716
G1 X180.423 Y33.716
G1 X180.557 Y33.583
G1 X185.722 Y28.417 E.22446
G1 X185.856 Y28.284
G1 X185.322 Y28.284
G1 X185.189 Y28.417
G1 X180.023 Y33.583 E.22446
G1 X179.89 Y33.716
G1 X179.356 Y33.716
G1 X179.49 Y33.583
G1 X184.655 Y28.417 E.22446
G1 X184.789 Y28.284
G1 X184.256 Y28.284
G1 X184.122 Y28.417
G1 X178.957 Y33.583 E.22446
G1 X178.823 Y33.716
G1 X178.29 Y33.716
G1 X178.424 Y33.583
G1 X183.589 Y28.417 E.22446
G1 X183.722 Y28.284
G1 X183.189 Y28.284
G1 X183.056 Y28.417
G1 X177.89 Y33.583 E.22446
G1 X177.757 Y33.716
G1 X177.223 Y33.716
G1 X177.357 Y33.583
G1 X182.522 Y28.417 E.22446
G1 X182.656 Y28.284
G1 X182.123 Y28.284
G1 X181.989 Y28.417
G1 X176.824 Y33.583 E.22446
G1 X176.69 Y33.716
G1 X176.157 Y33.716
G1 X176.291 Y33.583
G1 X181.456 Y28.417 E.22446
G1 X181.589 Y28.284
G1 X181.056 Y28.284
G1 X180.923 Y28.417
G1 X175.757 Y33.583 E.22446
G1 X175.624 Y33.716
G1 X175.09 Y33.716
G1 X175.224 Y33.583
G1 X180.389 Y28.417 E.22446
G1 X180.523 Y28.284
G1 X179.99 Y28.284
G1 X179.856 Y28.417
G1 X174.691 Y33.583 E.22446
G1 X174.557 Y33.716
G1 X174.024 Y33.716
G1 X174.158 Y33.583
G1 X179.323 Y28.417 E.22446
G1 X179.456 Y28.284
G1 X178.923 Y28.284
G1 X178.79 Y28.417
G1 X173.624 Y33.583 E.22446
G1 X173.491 Y33.716
G1 X172.957 Y33.716
G1 X173.091 Y33.583
G1 X178.256 Y28.417 E.22446
G1 X178.39 Y28.284
G1 X177.857 Y28.284
G1 X177.723 Y28.417
G1 X172.558 Y33.583 E.22446
G1 X172.424 Y33.716
G1 X171.891 Y33.716
G1 X172.025 Y33.583
G1 X177.19 Y28.417 E.22446
G1 X177.323 Y28.284
G1 X176.79 Y28.284
G1 X176.656 Y28.417
G1 X171.491 Y33.583 E.22446
G1 X171.358 Y33.716
G1 X170.824 Y33.716
G1 X170.958 Y33.583
G1 X176.123 Y28.417 E.22446
G1 X176.257 Y28.284
G1 X175.724 Y28.284
G1 X175.59 Y28.417
G1 X170.425 Y33.583 E.22446
G1 X170.291 Y33.716
M73 P89 R2
G1 X169.758 Y33.716
G1 X169.891 Y33.583
G1 X175.057 Y28.417 E.22446
G1 X175.19 Y28.284
G1 X174.657 Y28.284
G1 X174.523 Y28.417
G1 X169.358 Y33.583 E.22446
G1 X169.225 Y33.716
G1 X168.691 Y33.716
G1 X168.825 Y33.583
G1 X173.99 Y28.417 E.22446
G1 X174.124 Y28.284
G1 X173.591 Y28.284
G1 X173.457 Y28.417
G1 X168.292 Y33.583 E.22446
G1 X168.158 Y33.716
G1 X167.625 Y33.716
G1 X167.758 Y33.583
G1 X172.924 Y28.417 E.22446
G1 X173.057 Y28.284
G1 X172.524 Y28.284
G1 X172.39 Y28.417
G1 X167.225 Y33.583 E.22446
G1 X167.092 Y33.716
G1 X166.558 Y33.716
G1 X166.692 Y33.583
G1 X171.857 Y28.417 E.22446
G1 X171.991 Y28.284
G1 X171.458 Y28.284
G1 X171.324 Y28.417
G1 X166.159 Y33.583 E.22446
G1 X166.025 Y33.716
G1 X165.492 Y33.716
G1 X165.625 Y33.583
G1 X170.791 Y28.417 E.22446
G1 X170.924 Y28.284
G1 X170.391 Y28.284
G1 X170.257 Y28.417
G1 X165.092 Y33.583 E.22446
G1 X164.959 Y33.716
G1 X164.425 Y33.716
G1 X164.559 Y33.583
G1 X169.724 Y28.417 E.22446
G1 X169.858 Y28.284
G1 X169.325 Y28.284
G1 X169.191 Y28.417
G1 X164.026 Y33.583 E.22446
G1 X163.892 Y33.716
G1 X163.359 Y33.716
G1 X163.492 Y33.583
G1 X168.658 Y28.417 E.22446
G1 X168.791 Y28.284
G1 X168.258 Y28.284
G1 X168.124 Y28.417
G1 X162.959 Y33.583 E.22446
G1 X162.825 Y33.716
G1 X162.292 Y33.716
G1 X162.426 Y33.583
G1 X167.591 Y28.417 E.22446
G1 X167.725 Y28.284
G1 X167.192 Y28.284
G1 X167.058 Y28.417
G1 X161.893 Y33.583 E.22446
G1 X161.759 Y33.716
G1 X161.226 Y33.716
G1 X161.359 Y33.583
G1 X166.525 Y28.417 E.22446
G1 X166.658 Y28.284
G1 X166.125 Y28.284
G1 X165.991 Y28.417
G1 X160.826 Y33.583 E.22446
G1 X160.692 Y33.716
G1 X160.159 Y33.716
G1 X160.293 Y33.583
G1 X165.458 Y28.417 E.22446
G1 X165.592 Y28.284
G1 X165.058 Y28.284
G1 X164.925 Y28.417
G1 X159.76 Y33.583 E.22446
G1 X159.626 Y33.716
G1 X159.093 Y33.716
G1 X159.226 Y33.583
G1 X164.392 Y28.417 E.22446
G1 X164.525 Y28.284
G1 X163.992 Y28.284
G1 X163.858 Y28.417
G1 X158.693 Y33.583 E.22446
G1 X158.559 Y33.716
G1 X158.026 Y33.716
G1 X158.16 Y33.583
G1 X163.325 Y28.417 E.22446
G1 X163.459 Y28.284
G1 X162.925 Y28.284
G1 X162.792 Y28.417
G1 X157.627 Y33.583 E.22446
G1 X157.493 Y33.716
G1 X156.96 Y33.716
G1 X157.093 Y33.583
G1 X162.259 Y28.417 E.22445
G1 X162.392 Y28.284
G1 X161.859 Y28.284
G1 X161.725 Y28.417
G1 X156.56 Y33.583 E.22445
G1 X156.426 Y33.716
G1 X155.893 Y33.716
G1 X156.027 Y33.583
G1 X161.192 Y28.417 E.22446
G1 X161.326 Y28.284
G1 X160.792 Y28.284
G1 X160.659 Y28.417
G1 X155.494 Y33.583 E.22446
G1 X155.36 Y33.716
G1 X154.827 Y33.716
G1 X154.96 Y33.583
G1 X160.126 Y28.417 E.22445
G1 X160.259 Y28.284
G1 X159.726 Y28.284
G1 X159.592 Y28.417
G1 X154.427 Y33.583 E.22445
G1 X154.293 Y33.716
G1 X153.76 Y33.716
G1 X153.894 Y33.583
G1 X159.059 Y28.417 E.22446
G1 X159.193 Y28.284
G1 X158.659 Y28.284
G1 X158.526 Y28.417
G1 X153.36 Y33.583 E.22446
G1 X153.227 Y33.716
G1 X152.694 Y33.716
G1 X152.827 Y33.583
G1 X157.992 Y28.417 E.22445
G1 X158.126 Y28.284
G1 X157.593 Y28.284
G1 X157.459 Y28.417
G1 X152.294 Y33.583 E.22445
G1 X152.16 Y33.716
G1 X151.627 Y33.716
G1 X151.761 Y33.583
G1 X156.926 Y28.417 E.22446
G1 X157.06 Y28.284
G1 X156.526 Y28.284
G1 X156.393 Y28.417
G1 X151.227 Y33.583 E.22446
G1 X151.094 Y33.716
G1 X150.561 Y33.716
G1 X150.694 Y33.583
G1 X155.859 Y28.417 E.22445
G1 X155.993 Y28.284
G1 X155.46 Y28.284
G1 X155.326 Y28.417
G1 X150.161 Y33.583 E.22445
G1 X150.027 Y33.716
G1 X149.494 Y33.716
G1 X149.628 Y33.583
G1 X154.793 Y28.417 E.22446
G1 X154.927 Y28.284
G1 X154.393 Y28.284
G1 X154.26 Y28.417
G1 X149.094 Y33.583 E.22446
G1 X148.961 Y33.716
G1 X148.428 Y33.716
G1 X148.561 Y33.583
G1 X153.726 Y28.417 E.22445
G1 X153.86 Y28.284
G1 X153.327 Y28.284
G1 X153.193 Y28.417
G1 X148.028 Y33.583 E.22445
G1 X147.894 Y33.716
G1 X147.361 Y33.716
G1 X147.495 Y33.583
G1 X152.66 Y28.417 E.22446
G1 X152.794 Y28.284
G1 X152.26 Y28.284
G1 X152.127 Y28.417
G1 X146.961 Y33.583 E.22446
G1 X146.828 Y33.716
G1 X146.294 Y33.716
G1 X146.428 Y33.583
G1 X151.593 Y28.417 E.22446
G1 X151.727 Y28.284
G1 X151.194 Y28.284
G1 X151.06 Y28.417
G1 X145.895 Y33.583 E.22446
G1 X145.761 Y33.716
G1 X145.228 Y33.716
G1 X145.362 Y33.583
G1 X150.527 Y28.417 E.22446
G1 X150.661 Y28.284
G1 X150.127 Y28.284
G1 X149.994 Y28.417
G1 X144.828 Y33.583 E.22446
G1 X144.695 Y33.716
G1 X144.161 Y33.716
G1 X144.295 Y33.583
G1 X149.46 Y28.417 E.22446
G1 X149.594 Y28.284
G1 X149.061 Y28.284
G1 X148.927 Y28.417
G1 X143.762 Y33.583 E.22446
G1 X143.628 Y33.716
G1 X143.095 Y33.716
G1 X143.229 Y33.583
G1 X148.394 Y28.417 E.22446
G1 X148.527 Y28.284
G1 X147.994 Y28.284
G1 X147.861 Y28.417
G1 X142.695 Y33.583 E.22446
G1 X142.562 Y33.716
G1 X142.028 Y33.716
G1 X142.162 Y33.583
G1 X147.327 Y28.417 E.22446
G1 X147.461 Y28.284
G1 X146.928 Y28.284
G1 X146.794 Y28.417
G1 X141.629 Y33.583 E.22446
G1 X141.495 Y33.716
G1 X140.962 Y33.716
G1 X141.096 Y33.583
G1 X146.261 Y28.417 E.22446
G1 X146.394 Y28.284
G1 X145.861 Y28.284
G1 X145.728 Y28.417
G1 X140.562 Y33.583 E.22446
G1 X140.429 Y33.716
G1 X139.895 Y33.716
G1 X140.029 Y33.583
G1 X145.194 Y28.417 E.22446
G1 X145.328 Y28.284
G1 X144.795 Y28.284
G1 X144.661 Y28.417
G1 X139.496 Y33.583 E.22446
G1 X139.362 Y33.716
G1 X138.829 Y33.716
G1 X138.963 Y33.583
G1 X144.128 Y28.417 E.22446
G1 X144.261 Y28.284
G1 X143.728 Y28.284
G1 X143.595 Y28.417
G1 X138.429 Y33.583 E.22446
G1 X138.296 Y33.716
G1 X137.762 Y33.716
G1 X137.896 Y33.583
G1 X143.061 Y28.417 E.22446
G1 X143.195 Y28.284
G1 X142.662 Y28.284
G1 X142.528 Y28.417
G1 X137.363 Y33.583 E.22446
G1 X137.229 Y33.716
G1 X136.696 Y33.716
G1 X136.829 Y33.583
G1 X141.995 Y28.417 E.22446
G1 X142.128 Y28.284
G1 X141.595 Y28.284
G1 X141.461 Y28.417
G1 X136.296 Y33.583 E.22446
G1 X136.163 Y33.716
G1 X135.629 Y33.716
G1 X135.763 Y33.583
G1 X140.928 Y28.417 E.22446
G1 X141.062 Y28.284
G1 X140.529 Y28.284
G1 X140.395 Y28.417
G1 X135.23 Y33.583 E.22446
G1 X135.096 Y33.716
G1 X134.563 Y33.716
G1 X134.696 Y33.583
G1 X139.862 Y28.417 E.22446
G1 X139.995 Y28.284
G1 X139.462 Y28.284
G1 X139.328 Y28.417
G1 X134.163 Y33.583 E.22446
G1 X134.03 Y33.716
G1 X133.496 Y33.716
G1 X133.63 Y33.583
G1 X138.795 Y28.417 E.22446
G1 X138.929 Y28.284
G1 X138.396 Y28.284
G1 X138.262 Y28.417
G1 X133.097 Y33.583 E.22446
G1 X132.963 Y33.716
G1 X132.43 Y33.716
G1 X132.563 Y33.583
G1 X137.729 Y28.417 E.22446
G1 X137.862 Y28.284
G1 X137.329 Y28.284
G1 X137.195 Y28.417
G1 X132.03 Y33.583 E.22446
G1 X131.897 Y33.716
G1 X131.363 Y33.716
G1 X131.497 Y33.583
G1 X136.662 Y28.417 E.22446
G1 X136.796 Y28.284
G1 X136.263 Y28.284
G1 X136.129 Y28.417
G1 X130.964 Y33.583 E.22446
G1 X130.83 Y33.716
G1 X130.297 Y33.716
G1 X130.43 Y33.583
G1 X135.596 Y28.417 E.22446
G1 X135.729 Y28.284
G1 X135.196 Y28.284
G1 X135.062 Y28.417
G1 X129.897 Y33.583 E.22446
G1 X129.764 Y33.716
G1 X129.23 Y33.716
G1 X129.364 Y33.583
G1 X134.529 Y28.417 E.22446
G1 X134.663 Y28.284
G1 X134.13 Y28.284
G1 X133.996 Y28.417
G1 X128.831 Y33.583 E.22446
G1 X128.697 Y33.716
G1 X128.164 Y33.716
G1 X128.297 Y33.583
G1 X133.463 Y28.417 E.22446
G1 X133.596 Y28.284
G1 X133.063 Y28.284
G1 X132.929 Y28.417
G1 X127.764 Y33.583 E.22446
G1 X127.63 Y33.716
G1 X127.097 Y33.716
G1 X127.231 Y33.583
G1 X132.396 Y28.417 E.22446
G1 X132.53 Y28.284
G1 X131.996 Y28.284
G1 X131.863 Y28.417
G1 X126.698 Y33.583 E.22446
G1 X126.564 Y33.716
G1 X126.031 Y33.716
G1 X126.164 Y33.583
G1 X131.33 Y28.417 E.22446
G1 X131.463 Y28.284
G1 X130.93 Y28.284
G1 X130.796 Y28.417
G1 X125.631 Y33.583 E.22446
G1 X125.497 Y33.716
G1 X124.964 Y33.716
G1 X125.098 Y33.583
G1 X130.263 Y28.417 E.22446
G1 X130.397 Y28.284
G1 X129.863 Y28.284
G1 X129.73 Y28.417
G1 X124.565 Y33.583 E.22446
G1 X124.431 Y33.716
G1 X123.898 Y33.716
G1 X124.031 Y33.583
G1 X129.197 Y28.417 E.22446
G1 X129.33 Y28.284
G1 X128.797 Y28.284
G1 X128.663 Y28.417
G1 X123.498 Y33.583 E.22446
G1 X123.364 Y33.716
G1 X122.831 Y33.716
G1 X122.965 Y33.583
G1 X128.13 Y28.417 E.22446
G1 X128.264 Y28.284
G1 X127.73 Y28.284
G1 X127.597 Y28.417
G1 X122.432 Y33.583 E.22446
G1 X122.298 Y33.716
G1 X121.765 Y33.716
G1 X121.898 Y33.583
G1 X127.064 Y28.417 E.22446
G1 X127.197 Y28.284
G1 X126.664 Y28.284
G1 X126.53 Y28.417
G1 X121.365 Y33.583 E.22445
G1 X121.231 Y33.716
G1 X120.698 Y33.716
G1 X120.832 Y33.583
G1 X125.997 Y28.417 E.22445
G1 X126.131 Y28.284
G1 X125.597 Y28.284
G1 X125.464 Y28.417
G1 X120.299 Y33.583 E.22446
G1 X120.165 Y33.716
G1 X119.632 Y33.716
G1 X119.765 Y33.583
G1 X124.931 Y28.417 E.22446
G1 X125.064 Y28.284
G1 X124.531 Y28.284
G1 X124.397 Y28.417
G1 X119.232 Y33.583 E.22446
G1 X119.098 Y33.716
G1 X118.565 Y33.716
G1 X118.699 Y33.583
G1 X123.864 Y28.417 E.22445
G1 X123.998 Y28.284
G1 X123.464 Y28.284
G1 X123.331 Y28.417
G1 X118.165 Y33.583 E.22446
G1 X118.032 Y33.716
G1 X117.499 Y33.716
G1 X117.632 Y33.583
G1 X122.797 Y28.417 E.22446
G1 X122.931 Y28.284
G1 X122.398 Y28.284
G1 X122.264 Y28.417
G1 X117.099 Y33.583 E.22446
G1 X116.965 Y33.716
G1 X116.432 Y33.716
G1 X116.566 Y33.583
G1 X121.731 Y28.417 E.22445
G1 X121.865 Y28.284
G1 X121.331 Y28.284
G1 X121.198 Y28.417
G1 X116.032 Y33.583 E.22446
G1 X115.899 Y33.716
G1 X115.366 Y33.716
G1 X115.499 Y33.583
G1 X120.664 Y28.417 E.22446
G1 X120.798 Y28.284
G1 X120.265 Y28.284
G1 X120.131 Y28.417
G1 X114.966 Y33.583 E.22446
G1 X114.832 Y33.716
G1 X114.299 Y33.716
G1 X114.433 Y33.583
G1 X119.598 Y28.417 E.22445
G1 X119.732 Y28.284
G1 X119.198 Y28.284
G1 X119.065 Y28.417
G1 X113.899 Y33.583 E.22446
G1 X113.766 Y33.716
G1 X113.233 Y33.716
G1 X113.366 Y33.583
G1 X118.531 Y28.417 E.22446
G1 X118.665 Y28.284
G1 X118.132 Y28.284
G1 X117.998 Y28.417
G1 X112.833 Y33.583 E.22446
G1 X112.699 Y33.716
G1 X112.166 Y33.716
G1 X112.3 Y33.583
G1 X117.465 Y28.417 E.22445
G1 X117.599 Y28.284
G1 X117.065 Y28.284
G1 X116.932 Y28.417
G1 X111.766 Y33.583 E.22446
G1 X111.633 Y33.716
G1 X111.099 Y33.716
G1 X111.233 Y33.583
G1 X116.398 Y28.417 E.22446
G1 X116.532 Y28.284
G1 X115.999 Y28.284
G1 X115.865 Y28.417
G1 X110.7 Y33.583 E.22446
G1 X110.566 Y33.716
G1 X110.033 Y33.716
G1 X110.167 Y33.583
G1 X115.332 Y28.417 E.22445
G1 X115.466 Y28.284
G1 X114.932 Y28.284
M73 P90 R2
G1 X114.799 Y28.417
G1 X109.633 Y33.583 E.22446
G1 X109.5 Y33.716
G1 X108.966 Y33.716
G1 X109.1 Y33.583
G1 X114.265 Y28.417 E.22446
G1 X114.399 Y28.284
G1 X113.866 Y28.284
G1 X113.732 Y28.417
G1 X108.567 Y33.583 E.22446
G1 X108.433 Y33.716
G1 X107.9 Y33.716
G1 X108.034 Y33.583
G1 X113.199 Y28.417 E.22446
G1 X113.332 Y28.284
G1 X112.799 Y28.284
G1 X112.666 Y28.417
G1 X107.5 Y33.583 E.22446
G1 X107.367 Y33.716
G1 X106.833 Y33.716
G1 X106.967 Y33.583
G1 X112.132 Y28.417 E.22446
G1 X112.266 Y28.284
G1 X111.733 Y28.284
G1 X111.599 Y28.417
G1 X106.434 Y33.583 E.22446
G1 X106.3 Y33.716
G1 X105.767 Y33.716
G1 X105.901 Y33.583
G1 X111.066 Y28.417 E.22446
G1 X111.199 Y28.284
G1 X110.666 Y28.284
G1 X110.533 Y28.417
G1 X105.367 Y33.583 E.22446
G1 X105.234 Y33.716
G1 X104.7 Y33.716
G1 X104.834 Y33.583
G1 X109.999 Y28.417 E.22446
G1 X110.133 Y28.284
G1 X109.6 Y28.284
G1 X109.466 Y28.417
G1 X104.301 Y33.583 E.22446
G1 X104.167 Y33.716
G1 X103.634 Y33.716
G1 X103.768 Y33.583
G1 X108.933 Y28.417 E.22446
G1 X109.066 Y28.284
G1 X108.533 Y28.284
G1 X108.4 Y28.417
G1 X103.234 Y33.583 E.22446
G1 X103.101 Y33.716
G1 X102.567 Y33.716
G1 X102.701 Y33.583
G1 X107.866 Y28.417 E.22446
G1 X108 Y28.284
G1 X107.467 Y28.284
G1 X107.333 Y28.417
G1 X102.168 Y33.583 E.22446
G1 X102.034 Y33.716
G1 X101.501 Y33.716
G1 X101.634 Y33.583
G1 X106.8 Y28.417 E.22446
G1 X106.933 Y28.284
G1 X106.4 Y28.284
G1 X106.266 Y28.417
G1 X101.101 Y33.583 E.22446
G1 X100.968 Y33.716
G1 X100.434 Y33.716
G1 X100.568 Y33.583
G1 X105.733 Y28.417 E.22446
G1 X105.867 Y28.284
G1 X105.334 Y28.284
G1 X105.2 Y28.417
G1 X100.035 Y33.583 E.22446
G1 X99.901 Y33.716
G1 X99.368 Y33.716
G1 X99.501 Y33.583
G1 X104.667 Y28.417 E.22446
G1 X104.8 Y28.284
G1 X104.267 Y28.284
G1 X104.133 Y28.417
G1 X98.968 Y33.583 E.22446
G1 X98.835 Y33.716
G1 X98.301 Y33.716
G1 X98.435 Y33.583
G1 X103.6 Y28.417 E.22446
G1 X103.734 Y28.284
G1 X103.201 Y28.284
G1 X103.067 Y28.417
G1 X97.902 Y33.583 E.22446
G1 X97.768 Y33.716
G1 X97.235 Y33.716
G1 X97.368 Y33.583
G1 X102.534 Y28.417 E.22446
G1 X102.667 Y28.284
G1 X102.134 Y28.284
G1 X102 Y28.417
G1 X96.835 Y33.583 E.22446
G1 X96.702 Y33.716
G1 X96.168 Y33.716
G1 X96.302 Y33.583
G1 X101.467 Y28.417 E.22446
G1 X101.601 Y28.284
G1 X101.068 Y28.284
G1 X100.934 Y28.417
G1 X95.769 Y33.583 E.22446
G1 X95.635 Y33.716
G1 X95.102 Y33.716
G1 X95.235 Y33.583
G1 X100.401 Y28.417 E.22446
G1 X100.534 Y28.284
G1 X100.001 Y28.284
G1 X99.867 Y28.417
G1 X94.702 Y33.583 E.22446
G1 X94.569 Y33.716
G1 X94.035 Y33.716
G1 X94.169 Y33.583
G1 X99.334 Y28.417 E.22446
G1 X99.468 Y28.284
G1 X98.935 Y28.284
G1 X98.801 Y28.417
G1 X93.636 Y33.583 E.22446
G1 X93.502 Y33.716
G1 X92.969 Y33.716
G1 X93.102 Y33.583
G1 X98.268 Y28.417 E.22446
G1 X98.401 Y28.284
G1 X97.868 Y28.284
G1 X97.734 Y28.417
G1 X92.569 Y33.583 E.22446
G1 X92.435 Y33.716
G1 X91.902 Y33.716
G1 X92.036 Y33.583
G1 X97.201 Y28.417 E.22446
G1 X97.335 Y28.284
G1 X96.801 Y28.284
G1 X96.668 Y28.417
G1 X91.503 Y33.583 E.22446
G1 X91.369 Y33.716
G1 X90.836 Y33.716
G1 X90.969 Y33.583
G1 X96.135 Y28.417 E.22446
G1 X96.268 Y28.284
G1 X95.735 Y28.284
G1 X95.601 Y28.417
G1 X90.436 Y33.583 E.22446
G1 X90.302 Y33.716
G1 X89.769 Y33.716
G1 X89.903 Y33.583
G1 X95.068 Y28.417 E.22446
G1 X95.202 Y28.284
G1 X94.668 Y28.284
G1 X94.535 Y28.417
G1 X89.37 Y33.583 E.22446
G1 X89.236 Y33.716
G1 X88.703 Y33.716
G1 X88.836 Y33.583
G1 X94.002 Y28.417 E.22446
G1 X94.135 Y28.284
G1 X93.602 Y28.284
G1 X93.468 Y28.417
G1 X88.303 Y33.583 E.22446
G1 X88.169 Y33.716
G1 X87.636 Y33.716
G1 X87.77 Y33.583
G1 X92.935 Y28.417 E.22446
G1 X93.069 Y28.284
G1 X92.535 Y28.284
G1 X92.402 Y28.417
G1 X87.237 Y33.583 E.22445
G1 X87.103 Y33.716
G1 X86.57 Y33.716
G1 X86.703 Y33.583
G1 X91.869 Y28.417 E.22445
G1 X92.002 Y28.284
G1 X91.469 Y28.284
G1 X91.335 Y28.417
G1 X86.17 Y33.583 E.22445
G1 X86.036 Y33.716
G1 X85.503 Y33.716
G1 X85.637 Y33.583
G1 X90.802 Y28.417 E.22446
G1 X90.936 Y28.284
G1 X90.402 Y28.284
G1 X90.269 Y28.417
G1 X85.104 Y33.583 E.22445
G1 X84.97 Y33.716
G1 X84.437 Y33.716
G1 X84.57 Y33.583
G1 X89.736 Y28.417 E.22446
G1 X89.869 Y28.284
G1 X89.336 Y28.284
G1 X89.202 Y28.417
G1 X84.037 Y33.583 E.22446
G1 X83.903 Y33.716
G1 X83.37 Y33.716
G1 X83.504 Y33.583
G1 X88.669 Y28.417 E.22446
G1 X88.803 Y28.284
G1 X88.269 Y28.284
G1 X88.136 Y28.417
G1 X82.97 Y33.583 E.22445
G1 X82.837 Y33.716
G1 X82.304 Y33.716
G1 X82.437 Y33.583
G1 X87.602 Y28.417 E.22446
G1 X87.736 Y28.284
G1 X87.203 Y28.284
G1 X87.069 Y28.417
G1 X81.904 Y33.583 E.22446
G1 X81.77 Y33.716
G1 X81.237 Y33.716
G1 X81.371 Y33.583
G1 X86.536 Y28.417 E.22446
G1 X86.67 Y28.284
G1 X86.136 Y28.284
G1 X86.003 Y28.417
G1 X80.837 Y33.583 E.22445
G1 X80.704 Y33.716
G1 X80.171 Y33.716
G1 X80.304 Y33.583
G1 X85.469 Y28.417 E.22446
G1 X85.603 Y28.284
G1 X85.07 Y28.284
G1 X84.936 Y28.417
G1 X79.771 Y33.583 E.22446
G1 X79.637 Y33.716
G1 X79.104 Y33.716
G1 X79.238 Y33.583
G1 X84.403 Y28.417 E.22446
G1 X84.537 Y28.284
G1 X84.003 Y28.284
G1 X83.87 Y28.417
G1 X78.704 Y33.583 E.22445
G1 X78.571 Y33.716
G1 X78.038 Y33.716
G1 X78.171 Y33.583
G1 X83.336 Y28.417 E.22446
G1 X83.47 Y28.284
G1 X82.937 Y28.284
G1 X82.803 Y28.417
G1 X77.638 Y33.583 E.22446
G1 X77.504 Y33.716
G1 X76.971 Y33.716
G1 X77.105 Y33.583
G1 X82.27 Y28.417 E.22446
G1 X82.404 Y28.284
G1 X81.87 Y28.284
G1 X81.737 Y28.417
G1 X76.571 Y33.583 E.22445
G1 X76.438 Y33.716
G1 X75.904 Y33.716
G1 X76.038 Y33.583
G1 X81.203 Y28.417 E.22446
G1 X81.337 Y28.284
G1 X80.804 Y28.284
G1 X80.67 Y28.417
G1 X75.505 Y33.583 E.22446
G1 X75.371 Y33.716
G1 X74.838 Y33.716
G1 X74.972 Y33.583
G1 X80.137 Y28.417 E.22446
G1 X80.271 Y28.284
G1 X79.737 Y28.284
G1 X79.604 Y28.417
G1 X74.438 Y33.583 E.22445
G1 X74.305 Y33.716
G1 X73.771 Y33.716
G1 X73.905 Y33.583
G1 X79.07 Y28.417 E.22446
G1 X79.204 Y28.284
G1 X78.671 Y28.284
G1 X78.537 Y28.417
G1 X73.372 Y33.583 E.22446
G1 X73.238 Y33.716
G1 X72.705 Y33.716
G1 X72.839 Y33.583
G1 X78.004 Y28.417 E.22446
G1 X78.137 Y28.284
G1 X77.604 Y28.284
G1 X77.471 Y28.417
G1 X72.305 Y33.583 E.22445
G1 X72.172 Y33.716
G1 X71.638 Y33.716
G1 X71.772 Y33.583
G1 X76.937 Y28.417 E.22446
G1 X77.071 Y28.284
G1 X76.538 Y28.284
G1 X76.404 Y28.417
G1 X71.239 Y33.583 E.22446
G1 X71.105 Y33.716
G1 X70.572 Y33.716
G1 X70.706 Y33.583
G1 X75.871 Y28.417 E.22446
G1 X76.004 Y28.284
G1 X75.471 Y28.284
G1 X75.338 Y28.417
G1 X70.172 Y33.583 E.22445
G1 X70.039 Y33.716
G1 X69.505 Y33.716
G1 X69.639 Y33.583
G1 X74.804 Y28.417 E.22446
G1 X74.938 Y28.284
G1 X74.405 Y28.284
G1 X74.271 Y28.417
G1 X69.106 Y33.583 E.22446
G1 X68.972 Y33.716
G1 X68.439 Y33.716
G1 X68.573 Y33.583
G1 X73.738 Y28.417 E.22446
G1 X73.871 Y28.284
G1 X73.338 Y28.284
G1 X73.205 Y28.417
G1 X68.039 Y33.583 E.22446
G1 X67.906 Y33.716
G1 X67.372 Y33.716
G1 X67.506 Y33.583
G1 X72.671 Y28.417 E.22446
G1 X72.805 Y28.284
G1 X72.272 Y28.284
G1 X72.138 Y28.417
G1 X66.973 Y33.583 E.22446
G1 X66.839 Y33.716
G1 X66.306 Y33.716
G1 X66.439 Y33.583
G1 X71.605 Y28.417 E.22446
G1 X71.738 Y28.284
G1 X71.205 Y28.284
G1 X71.071 Y28.417
G1 X65.906 Y33.583 E.22446
G1 X65.773 Y33.716
G1 X65.239 Y33.716
G1 X65.373 Y33.583
G1 X70.538 Y28.417 E.22446
G1 X70.672 Y28.284
G1 X70.139 Y28.284
G1 X70.005 Y28.417
G1 X64.84 Y33.583 E.22446
G1 X64.706 Y33.716
G1 X64.173 Y33.716
G1 X64.306 Y33.583
G1 X69.472 Y28.417 E.22446
G1 X69.605 Y28.284
G1 X69.072 Y28.284
G1 X68.938 Y28.417
G1 X63.773 Y33.583 E.22446
M73 P90 R1
G1 X63.64 Y33.716
G1 X63.106 Y33.716
G1 X63.24 Y33.583
G1 X68.405 Y28.417 E.22446
G1 X68.539 Y28.284
G1 X68.006 Y28.284
G1 X67.872 Y28.417
G1 X62.707 Y33.583 E.22446
G1 X62.573 Y33.716
G1 X62.04 Y33.716
G1 X62.173 Y33.583
G1 X67.339 Y28.417 E.22446
G1 X67.472 Y28.284
G1 X66.939 Y28.284
G1 X66.805 Y28.417
G1 X61.64 Y33.583 E.22446
G1 X61.507 Y33.716
G1 X60.973 Y33.716
G1 X61.107 Y33.583
G1 X66.272 Y28.417 E.22446
G1 X66.406 Y28.284
G1 X65.873 Y28.284
G1 X65.739 Y28.417
G1 X60.574 Y33.583 E.22446
G1 X60.44 Y33.716
G1 X59.907 Y33.716
G1 X60.04 Y33.583
G1 X65.206 Y28.417 E.22446
G1 X65.339 Y28.284
G1 X64.806 Y28.284
G1 X64.672 Y28.417
G1 X59.507 Y33.583 E.22446
G1 X59.374 Y33.716
G1 X58.84 Y33.716
G1 X58.974 Y33.583
G1 X64.139 Y28.417 E.22446
G1 X64.273 Y28.284
G1 X63.74 Y28.284
G1 X63.606 Y28.417
G1 X58.441 Y33.583 E.22446
G1 X58.307 Y33.716
G1 X57.774 Y33.716
G1 X57.907 Y33.583
G1 X63.073 Y28.417 E.22446
G1 X63.206 Y28.284
G1 X62.673 Y28.284
G1 X62.539 Y28.417
G1 X57.374 Y33.583 E.22446
G1 X57.24 Y33.716
G1 X56.707 Y33.716
G1 X56.841 Y33.583
G1 X62.006 Y28.417 E.22446
G1 X62.14 Y28.284
G1 X61.606 Y28.284
G1 X61.473 Y28.417
G1 X56.308 Y33.583 E.22446
G1 X56.174 Y33.716
G1 X55.641 Y33.716
G1 X55.774 Y33.583
G1 X60.94 Y28.417 E.22446
G1 X61.073 Y28.284
G1 X60.54 Y28.284
G1 X60.406 Y28.417
G1 X55.241 Y33.583 E.22446
G1 X55.107 Y33.716
G1 X54.574 Y33.716
G1 X54.708 Y33.583
G1 X59.873 Y28.417 E.22446
G1 X60.007 Y28.284
G1 X59.473 Y28.284
G1 X59.34 Y28.417
G1 X54.175 Y33.583 E.22446
G1 X54.041 Y33.716
G1 X53.508 Y33.716
G1 X53.641 Y33.583
G1 X58.807 Y28.417 E.22446
G1 X58.94 Y28.284
G1 X58.407 Y28.284
G1 X58.273 Y28.417
G1 X53.108 Y33.583 E.22446
G1 X52.974 Y33.716
G1 X52.441 Y33.716
G1 X52.575 Y33.583
G1 X57.74 Y28.417 E.22446
G1 X57.874 Y28.284
G1 X57.34 Y28.284
G1 X57.207 Y28.417
G1 X52.042 Y33.583 E.22446
G1 X51.908 Y33.716
G1 X51.375 Y33.716
G1 X51.508 Y33.583
G1 X56.674 Y28.417 E.22445
G1 X56.807 Y28.284
G1 X56.274 Y28.284
G1 X56.14 Y28.417
G1 X50.975 Y33.583 E.22445
G1 X50.841 Y33.716
G1 X50.308 Y33.716
G1 X50.442 Y33.583
G1 X55.607 Y28.417 E.22445
G1 X55.741 Y28.284
G1 X55.207 Y28.284
G1 X55.074 Y28.417
G1 X49.909 Y33.583 E.22445
G1 X49.775 Y33.716
G1 X49.242 Y33.716
G1 X49.375 Y33.583
M73 P91 R1
G1 X54.54 Y28.417 E.22445
G1 X54.674 Y28.284
G1 X54.141 Y28.284
G1 X54.007 Y28.417
G1 X48.842 Y33.583 E.22445
G1 X48.708 Y33.716
G1 X48.175 Y33.716
G1 X48.309 Y33.583
G1 X53.474 Y28.417 E.22445
G1 X53.608 Y28.284
G1 X53.074 Y28.284
G1 X52.941 Y28.417
G1 X47.775 Y33.583 E.22445
G1 X47.642 Y33.716
G1 X47.109 Y33.716
G1 X47.242 Y33.583
G1 X52.407 Y28.417 E.22445
G1 X52.541 Y28.284
G1 X52.008 Y28.284
G1 X51.874 Y28.417
G1 X46.709 Y33.583 E.22445
G1 X46.575 Y33.716
G1 X46.042 Y33.716
G1 X46.176 Y33.583
G1 X51.341 Y28.417 E.22445
G1 X51.475 Y28.284
G1 X50.941 Y28.284
G1 X50.808 Y28.417
G1 X45.642 Y33.583 E.22445
G1 X45.509 Y33.716
G1 X44.976 Y33.716
G1 X45.109 Y33.583
G1 X50.274 Y28.417 E.22445
G1 X50.408 Y28.284
G1 X49.875 Y28.284
G1 X49.741 Y28.417
G1 X44.576 Y33.583 E.22445
G1 X44.442 Y33.716
G1 X43.909 Y33.716
G1 X44.043 Y33.583
G1 X49.208 Y28.417 E.22445
G1 X49.342 Y28.284
G1 X48.808 Y28.284
G1 X48.675 Y28.417
G1 X43.509 Y33.583 E.22446
G1 X43.376 Y33.716
G1 X42.843 Y33.716
G1 X42.976 Y33.583
G1 X48.141 Y28.417 E.22445
G1 X48.275 Y28.284
G1 X47.742 Y28.284
G1 X47.608 Y28.417
G1 X42.443 Y33.583 E.22446
G1 X42.309 Y33.716
G1 X41.776 Y33.716
G1 X41.91 Y33.583
G1 X47.075 Y28.417 E.22446
G1 X47.209 Y28.284
G1 X46.675 Y28.284
G1 X46.542 Y28.417
G1 X41.376 Y33.583 E.22446
G1 X41.243 Y33.716
G1 X40.709 Y33.716
G1 X40.843 Y33.583
G1 X46.008 Y28.417 E.22445
G1 X46.142 Y28.284
G1 X45.609 Y28.284
G1 X45.475 Y28.417
G1 X40.31 Y33.583 E.22446
G1 X40.176 Y33.716
G1 X39.643 Y33.716
G1 X39.777 Y33.583
G1 X44.942 Y28.417 E.22446
G1 X45.076 Y28.284
G1 X44.542 Y28.284
G1 X44.409 Y28.417
G1 X39.243 Y33.583 E.22446
G1 X39.11 Y33.716
G1 X38.576 Y33.716
G1 X38.71 Y33.583
G1 X43.875 Y28.417 E.22445
G1 X44.009 Y28.284
G1 X43.476 Y28.284
G1 X43.342 Y28.417
G1 X38.177 Y33.583 E.22446
G1 X38.043 Y33.716
G1 X37.51 Y33.716
G1 X37.644 Y33.583
G1 X42.809 Y28.417 E.22446
G1 X42.942 Y28.284
G1 X42.409 Y28.284
G1 X42.276 Y28.417
G1 X37.11 Y33.583 E.22446
G1 X36.977 Y33.716
G1 X36.443 Y33.716
G1 X36.577 Y33.583
G1 X41.742 Y28.417 E.22445
G1 X41.876 Y28.284
G1 X41.343 Y28.284
G1 X41.209 Y28.417
G1 X36.044 Y33.583 E.22446
G1 X35.91 Y33.716
G1 X35.377 Y33.716
G1 X35.511 Y33.583
G1 X40.676 Y28.417 E.22446
G1 X40.809 Y28.284
G1 X40.276 Y28.284
G1 X40.143 Y28.417
G1 X34.977 Y33.583 E.22446
G1 X34.844 Y33.716
G1 X34.31 Y33.716
G1 X34.444 Y33.583
G1 X39.609 Y28.417 E.22445
G1 X39.743 Y28.284
G1 X39.21 Y28.284
G1 X39.076 Y28.417
G1 X33.911 Y33.583 E.22446
G1 X33.777 Y33.716
G1 X33.244 Y33.716
G1 X33.378 Y33.583
G1 X38.543 Y28.417 E.22446
G1 X38.676 Y28.284
G1 X38.143 Y28.284
G1 X38.01 Y28.417
G1 X32.844 Y33.583 E.22446
G1 X32.711 Y33.716
G1 X32.177 Y33.716
G1 X32.311 Y33.583
G1 X37.476 Y28.417 E.22445
G1 X37.61 Y28.284
G1 X37.077 Y28.284
G1 X36.943 Y28.417
G1 X31.778 Y33.583 E.22446
G1 X31.644 Y33.716
G1 X31.111 Y33.716
G1 X31.244 Y33.583
G1 X36.41 Y28.417 E.22446
G1 X36.543 Y28.284
G1 X36.01 Y28.284
G1 X35.876 Y28.417
G1 X30.711 Y33.583 E.22446
G1 X30.578 Y33.716
G1 X30.044 Y33.716
G1 X30.178 Y33.583
G1 X35.343 Y28.417 E.22445
G1 X35.477 Y28.284
G1 X34.944 Y28.284
G1 X34.81 Y28.417
G1 X29.645 Y33.583 E.22446
G1 X29.511 Y33.716
G1 X28.978 Y33.716
G1 X29.111 Y33.583
G1 X34.277 Y28.417 E.22446
G1 X34.41 Y28.284
G1 X33.877 Y28.284
G1 X33.743 Y28.417
G1 X28.578 Y33.583 E.22446
G1 X28.445 Y33.716
G1 X27.911 Y33.716
G1 X28.045 Y33.583
G1 X33.21 Y28.417 E.22446
G1 X33.344 Y28.284
G1 X32.811 Y28.284
G1 X32.677 Y28.417
G1 X27.512 Y33.583 E.22446
G1 X27.378 Y33.716
G1 X26.845 Y33.716
G1 X26.978 Y33.583
G1 X32.144 Y28.417 E.22446
G1 X32.277 Y28.284
G1 X31.744 Y28.284
G1 X31.61 Y28.417
G1 X26.445 Y33.583 E.22446
G1 X26.312 Y33.716
G1 X25.778 Y33.716
G1 X25.912 Y33.583
G1 X31.077 Y28.417 E.22446
G1 X31.211 Y28.284
G1 X30.678 Y28.284
G1 X30.544 Y28.417
G1 X25.379 Y33.583 E.22446
G1 X25.245 Y33.716
G1 X24.712 Y33.716
G1 X24.845 Y33.583
G1 X30.011 Y28.417 E.22446
G1 X30.144 Y28.284
G1 X29.611 Y28.284
G1 X29.477 Y28.417
G1 X24.312 Y33.583 E.22446
G1 X24.179 Y33.716
G1 X23.645 Y33.716
G1 X23.779 Y33.583
G1 X28.944 Y28.417 E.22446
G1 X29.078 Y28.284
G1 X28.545 Y28.284
G1 X28.411 Y28.417
G1 X23.246 Y33.583 E.22446
G1 X23.112 Y33.716
G1 X22.579 Y33.716
G1 X22.712 Y33.583
G1 X27.878 Y28.417 E.22446
G1 X28.011 Y28.284
G1 X27.478 Y28.284
G1 X27.344 Y28.417
G1 X22.179 Y33.583 E.22446
G1 X22.045 Y33.716
G1 X21.512 Y33.716
G1 X21.646 Y33.583
G1 X26.811 Y28.417 E.22446
G1 X26.945 Y28.284
G1 X26.411 Y28.284
G1 X26.278 Y28.417
G1 X21.113 Y33.583 E.22446
G1 X20.979 Y33.716
G1 X20.446 Y33.716
G1 X20.579 Y33.583
G1 X25.745 Y28.417 E.22446
G1 X25.878 Y28.284
G1 X25.345 Y28.284
G1 X25.211 Y28.417
G1 X20.046 Y33.583 E.22446
G1 X19.912 Y33.716
G1 X19.379 Y33.716
G1 X19.513 Y33.583
G1 X24.678 Y28.417 E.22446
G1 X24.812 Y28.284
G1 X24.278 Y28.284
G1 X24.145 Y28.417
G1 X18.98 Y33.583 E.22446
G1 X18.846 Y33.716
G1 X18.313 Y33.716
G1 X18.446 Y33.583
G1 X23.612 Y28.417 E.22446
G1 X23.745 Y28.284
G1 X23.212 Y28.284
G1 X23.078 Y28.417
G1 X17.913 Y33.583 E.22446
G1 X17.779 Y33.716
G1 X17.246 Y33.716
G1 X17.38 Y33.583
G1 X22.545 Y28.417 E.22446
G1 X22.679 Y28.284
G1 X22.145 Y28.284
G1 X22.012 Y28.417
G1 X16.847 Y33.583 E.22446
G1 X16.713 Y33.716
G1 X16.18 Y33.716
G1 X16.313 Y33.583
G1 X21.479 Y28.417 E.22446
G1 X21.612 Y28.284
G1 X21.079 Y28.284
G1 X20.945 Y28.417
G1 X15.78 Y33.583 E.22445
G1 X15.646 Y33.716
G1 X15.113 Y33.716
G1 X15.247 Y33.583
G1 X20.412 Y28.417 E.22445
G1 X20.546 Y28.284
G1 X20.012 Y28.284
G1 X19.879 Y28.417
G1 X14.713 Y33.583 E.22445
G1 X14.58 Y33.716
G1 X14.047 Y33.716
G1 X14.18 Y33.583
G1 X19.345 Y28.417 E.22445
G1 X19.479 Y28.284
G1 X18.946 Y28.284
G1 X18.812 Y28.417
G1 X13.647 Y33.583 E.22445
G1 X13.513 Y33.716
G1 X12.98 Y33.716
G1 X13.114 Y33.583
G1 X18.279 Y28.417 E.22445
G1 X18.413 Y28.284
G1 X17.879 Y28.284
G1 X17.746 Y28.417
G1 X12.58 Y33.583 E.22445
G1 X12.447 Y33.716
G1 X11.914 Y33.716
G1 X12.047 Y33.583
G1 X17.212 Y28.417 E.22445
G1 X17.346 Y28.284
G1 X16.813 Y28.284
G1 X16.679 Y28.417
G1 X11.514 Y33.583 E.22445
G1 X11.38 Y33.716
G1 X10.847 Y33.716
G1 X10.981 Y33.583
G1 X16.146 Y28.417 E.22445
G1 X16.28 Y28.284
G1 X15.746 Y28.284
G1 X15.613 Y28.417
G1 X10.447 Y33.583 E.22445
G1 X10.314 Y33.716
G1 X9.781 Y33.716
G1 X9.914 Y33.583
G1 X15.079 Y28.417 E.22445
G1 X15.213 Y28.284
G1 X14.68 Y28.284
G1 X14.546 Y28.417
G1 X9.381 Y33.583 E.22445
G1 X9.247 Y33.716
G1 X8.714 Y33.716
G1 X8.848 Y33.583
G1 X14.013 Y28.417 E.22445
; WIPE_START
M204 S10000
G1 X12.599 Y29.832 E-.76
; WIPE_END
G1 E-.04 F1800
G1 X18.38 Y34.815 Z1.6 F36000
G1 X241.987 Y227.583 Z1.6
G1 Z1.2
G1 E.8 F1800
G1 F11933.819
M204 S2000
G1 X247.152 Y222.417 E.22445
G1 X247.286 Y222.284
G1 X246.753 Y222.284
G1 X246.619 Y222.417
G1 X241.454 Y227.583 E.22445
G1 X241.32 Y227.716
G1 X240.787 Y227.716
G1 X240.92 Y227.583
G1 X246.086 Y222.417 E.22445
G1 X246.219 Y222.284
G1 X245.686 Y222.284
G1 X245.552 Y222.417
G1 X240.387 Y227.583 E.22445
G1 X240.254 Y227.716
G1 X239.72 Y227.716
G1 X239.854 Y227.583
G1 X245.019 Y222.417 E.22445
G1 X245.153 Y222.284
G1 X244.62 Y222.284
G1 X244.486 Y222.417
G1 X239.321 Y227.583 E.22445
G1 X239.187 Y227.716
G1 X238.654 Y227.716
G1 X238.787 Y227.583
G1 X243.953 Y222.417 E.22445
G1 X244.086 Y222.284
G1 X243.553 Y222.284
G1 X243.419 Y222.417
G1 X238.254 Y227.583 E.22445
G1 X238.12 Y227.716
G1 X237.587 Y227.716
G1 X237.721 Y227.583
G1 X242.886 Y222.417 E.22445
G1 X243.02 Y222.284
G1 X242.487 Y222.284
G1 X242.353 Y222.417
G1 X237.188 Y227.583 E.22445
G1 X237.054 Y227.716
G1 X236.521 Y227.716
G1 X236.654 Y227.583
G1 X241.82 Y222.417 E.22445
G1 X241.953 Y222.284
G1 X241.42 Y222.284
G1 X241.286 Y222.417
G1 X236.121 Y227.583 E.22445
G1 X235.987 Y227.716
G1 X235.454 Y227.716
G1 X235.588 Y227.583
G1 X240.753 Y222.417 E.22445
G1 X240.887 Y222.284
G1 X240.353 Y222.284
G1 X240.22 Y222.417
G1 X235.055 Y227.583 E.22445
G1 X234.921 Y227.716
G1 X234.388 Y227.716
G1 X234.521 Y227.583
G1 X239.687 Y222.417 E.22446
G1 X239.82 Y222.284
G1 X239.287 Y222.284
G1 X239.153 Y222.417
G1 X233.988 Y227.583 E.22446
G1 X233.854 Y227.716
G1 X233.321 Y227.716
G1 X233.455 Y227.583
G1 X238.62 Y222.417 E.22446
G1 X238.754 Y222.284
G1 X238.22 Y222.284
G1 X238.087 Y222.417
G1 X232.922 Y227.583 E.22446
G1 X232.788 Y227.716
G1 X232.255 Y227.716
G1 X232.388 Y227.583
G1 X237.554 Y222.417 E.22446
G1 X237.687 Y222.284
G1 X237.154 Y222.284
G1 X237.02 Y222.417
G1 X231.855 Y227.583 E.22446
G1 X231.721 Y227.716
G1 X231.188 Y227.716
G1 X231.322 Y227.583
G1 X236.487 Y222.417 E.22446
G1 X236.621 Y222.284
G1 X236.087 Y222.284
G1 X235.954 Y222.417
G1 X230.789 Y227.583 E.22446
G1 X230.655 Y227.716
G1 X230.122 Y227.716
G1 X230.255 Y227.583
G1 X235.421 Y222.417 E.22446
G1 X235.554 Y222.284
G1 X235.021 Y222.284
G1 X234.887 Y222.417
G1 X229.722 Y227.583 E.22446
G1 X229.588 Y227.716
G1 X229.055 Y227.716
G1 X229.189 Y227.583
G1 X234.354 Y222.417 E.22446
G1 X234.488 Y222.284
G1 X233.954 Y222.284
G1 X233.821 Y222.417
G1 X228.655 Y227.583 E.22446
G1 X228.522 Y227.716
G1 X227.989 Y227.716
G1 X228.122 Y227.583
G1 X233.287 Y222.417 E.22446
G1 X233.421 Y222.284
G1 X232.888 Y222.284
G1 X232.754 Y222.417
G1 X227.589 Y227.583 E.22446
G1 X227.455 Y227.716
G1 X226.922 Y227.716
G1 X227.056 Y227.583
G1 X232.221 Y222.417 E.22446
G1 X232.355 Y222.284
G1 X231.821 Y222.284
G1 X231.688 Y222.417
G1 X226.522 Y227.583 E.22446
G1 X226.389 Y227.716
G1 X225.856 Y227.716
G1 X225.989 Y227.583
M73 P92 R1
G1 X231.154 Y222.417 E.22446
G1 X231.288 Y222.284
G1 X230.755 Y222.284
G1 X230.621 Y222.417
G1 X225.456 Y227.583 E.22446
G1 X225.322 Y227.716
G1 X224.789 Y227.716
G1 X224.923 Y227.583
G1 X230.088 Y222.417 E.22446
G1 X230.222 Y222.284
G1 X229.688 Y222.284
G1 X229.555 Y222.417
G1 X224.389 Y227.583 E.22446
G1 X224.256 Y227.716
G1 X223.723 Y227.716
G1 X223.856 Y227.583
G1 X229.021 Y222.417 E.22446
G1 X229.155 Y222.284
G1 X228.622 Y222.284
G1 X228.488 Y222.417
G1 X223.323 Y227.583 E.22446
G1 X223.189 Y227.716
G1 X222.656 Y227.716
G1 X222.79 Y227.583
G1 X227.955 Y222.417 E.22446
G1 X228.089 Y222.284
G1 X227.555 Y222.284
G1 X227.422 Y222.417
G1 X222.256 Y227.583 E.22446
G1 X222.123 Y227.716
G1 X221.59 Y227.716
G1 X221.723 Y227.583
G1 X226.888 Y222.417 E.22446
G1 X227.022 Y222.284
G1 X226.489 Y222.284
G1 X226.355 Y222.417
G1 X221.19 Y227.583 E.22445
G1 X221.056 Y227.716
G1 X220.523 Y227.716
G1 X220.657 Y227.583
G1 X225.822 Y222.417 E.22446
G1 X225.956 Y222.284
G1 X225.422 Y222.284
G1 X225.289 Y222.417
G1 X220.123 Y227.583 E.22446
G1 X219.99 Y227.716
G1 X219.456 Y227.716
G1 X219.59 Y227.583
G1 X224.755 Y222.417 E.22446
G1 X224.889 Y222.284
G1 X224.356 Y222.284
G1 X224.222 Y222.417
G1 X219.057 Y227.583 E.22445
G1 X218.923 Y227.716
G1 X218.39 Y227.716
G1 X218.524 Y227.583
G1 X223.689 Y222.417 E.22446
G1 X223.822 Y222.284
G1 X223.289 Y222.284
G1 X223.156 Y222.417
G1 X217.99 Y227.583 E.22446
G1 X217.857 Y227.716
G1 X217.323 Y227.716
G1 X217.457 Y227.583
G1 X222.622 Y222.417 E.22446
G1 X222.756 Y222.284
G1 X222.223 Y222.284
G1 X222.089 Y222.417
G1 X216.924 Y227.583 E.22445
G1 X216.79 Y227.716
G1 X216.257 Y227.716
G1 X216.391 Y227.583
G1 X221.556 Y222.417 E.22446
G1 X221.689 Y222.284
G1 X221.156 Y222.284
G1 X221.023 Y222.417
G1 X215.857 Y227.583 E.22446
G1 X215.724 Y227.716
G1 X215.19 Y227.716
G1 X215.324 Y227.583
G1 X220.489 Y222.417 E.22446
G1 X220.623 Y222.284
G1 X220.09 Y222.284
G1 X219.956 Y222.417
G1 X214.791 Y227.583 E.22445
G1 X214.657 Y227.716
G1 X214.124 Y227.716
G1 X214.258 Y227.583
G1 X219.423 Y222.417 E.22446
G1 X219.556 Y222.284
G1 X219.023 Y222.284
G1 X218.89 Y222.417
G1 X213.724 Y227.583 E.22446
G1 X213.591 Y227.716
G1 X213.057 Y227.716
G1 X213.191 Y227.583
G1 X218.356 Y222.417 E.22446
G1 X218.49 Y222.284
G1 X217.957 Y222.284
G1 X217.823 Y222.417
G1 X212.658 Y227.583 E.22445
G1 X212.524 Y227.716
G1 X211.991 Y227.716
G1 X212.125 Y227.583
G1 X217.29 Y222.417 E.22446
G1 X217.423 Y222.284
G1 X216.89 Y222.284
G1 X216.757 Y222.417
G1 X211.591 Y227.583 E.22446
G1 X211.458 Y227.716
G1 X210.924 Y227.716
G1 X211.058 Y227.583
G1 X216.223 Y222.417 E.22446
G1 X216.357 Y222.284
G1 X215.824 Y222.284
G1 X215.69 Y222.417
G1 X210.525 Y227.583 E.22445
G1 X210.391 Y227.716
G1 X209.858 Y227.716
G1 X209.991 Y227.583
G1 X215.157 Y222.417 E.22446
G1 X215.29 Y222.284
G1 X214.757 Y222.284
G1 X214.623 Y222.417
G1 X209.458 Y227.583 E.22446
G1 X209.325 Y227.716
G1 X208.791 Y227.716
G1 X208.925 Y227.583
G1 X214.09 Y222.417 E.22446
G1 X214.224 Y222.284
G1 X213.691 Y222.284
G1 X213.557 Y222.417
G1 X208.392 Y227.583 E.22445
G1 X208.258 Y227.716
G1 X207.725 Y227.716
G1 X207.858 Y227.583
G1 X213.024 Y222.417 E.22446
G1 X213.157 Y222.284
G1 X212.624 Y222.284
G1 X212.49 Y222.417
G1 X207.325 Y227.583 E.22446
G1 X207.192 Y227.716
G1 X206.658 Y227.716
G1 X206.792 Y227.583
G1 X211.957 Y222.417 E.22445
G1 X212.091 Y222.284
G1 X211.558 Y222.284
G1 X211.424 Y222.417
G1 X206.259 Y227.583 E.22445
G1 X206.125 Y227.716
G1 X205.592 Y227.716
G1 X205.725 Y227.583
G1 X210.891 Y222.417 E.22445
G1 X211.024 Y222.284
G1 X210.491 Y222.284
G1 X210.357 Y222.417
G1 X205.192 Y227.583 E.22445
G1 X205.059 Y227.716
G1 X204.525 Y227.716
G1 X204.659 Y227.583
G1 X209.824 Y222.417 E.22445
G1 X209.958 Y222.284
G1 X209.425 Y222.284
G1 X209.291 Y222.417
G1 X204.126 Y227.583 E.22445
G1 X203.992 Y227.716
G1 X203.459 Y227.716
G1 X203.592 Y227.583
G1 X208.758 Y222.417 E.22445
G1 X208.891 Y222.284
G1 X208.358 Y222.284
G1 X208.224 Y222.417
G1 X203.059 Y227.583 E.22445
G1 X202.925 Y227.716
G1 X202.392 Y227.716
G1 X202.526 Y227.583
G1 X207.691 Y222.417 E.22445
G1 X207.825 Y222.284
G1 X207.292 Y222.284
G1 X207.158 Y222.417
G1 X201.993 Y227.583 E.22445
G1 X201.859 Y227.716
G1 X201.326 Y227.716
G1 X201.459 Y227.583
G1 X206.625 Y222.417 E.22445
G1 X206.758 Y222.284
G1 X206.225 Y222.284
G1 X206.091 Y222.417
G1 X200.926 Y227.583 E.22445
G1 X200.792 Y227.716
G1 X200.259 Y227.716
G1 X200.393 Y227.583
G1 X205.558 Y222.417 E.22445
G1 X205.692 Y222.284
G1 X205.158 Y222.284
G1 X205.025 Y222.417
G1 X199.86 Y227.583 E.22445
G1 X199.726 Y227.716
G1 X199.193 Y227.716
G1 X199.326 Y227.583
G1 X204.492 Y222.417 E.22445
G1 X204.625 Y222.284
G1 X204.092 Y222.284
G1 X203.958 Y222.417
G1 X198.793 Y227.583 E.22446
G1 X198.659 Y227.716
G1 X198.126 Y227.716
G1 X198.26 Y227.583
G1 X203.425 Y222.417 E.22446
G1 X203.559 Y222.284
G1 X203.025 Y222.284
G1 X202.892 Y222.417
G1 X197.727 Y227.583 E.22446
G1 X197.593 Y227.716
G1 X197.06 Y227.716
G1 X197.193 Y227.583
G1 X202.359 Y222.417 E.22446
G1 X202.492 Y222.284
G1 X201.959 Y222.284
G1 X201.825 Y222.417
G1 X196.66 Y227.583 E.22446
G1 X196.526 Y227.716
G1 X195.993 Y227.716
G1 X196.127 Y227.583
G1 X201.292 Y222.417 E.22446
G1 X201.426 Y222.284
G1 X200.892 Y222.284
G1 X200.759 Y222.417
G1 X195.594 Y227.583 E.22446
G1 X195.46 Y227.716
G1 X194.927 Y227.716
G1 X195.06 Y227.583
G1 X200.226 Y222.417 E.22446
G1 X200.359 Y222.284
G1 X199.826 Y222.284
G1 X199.692 Y222.417
G1 X194.527 Y227.583 E.22446
G1 X194.393 Y227.716
G1 X193.86 Y227.716
G1 X193.994 Y227.583
G1 X199.159 Y222.417 E.22446
G1 X199.293 Y222.284
G1 X198.759 Y222.284
G1 X198.626 Y222.417
G1 X193.46 Y227.583 E.22446
G1 X193.327 Y227.716
G1 X192.794 Y227.716
G1 X192.927 Y227.583
G1 X198.092 Y222.417 E.22446
G1 X198.226 Y222.284
G1 X197.693 Y222.284
G1 X197.559 Y222.417
G1 X192.394 Y227.583 E.22446
G1 X192.26 Y227.716
G1 X191.727 Y227.716
G1 X191.861 Y227.583
G1 X197.026 Y222.417 E.22446
G1 X197.16 Y222.284
G1 X196.626 Y222.284
G1 X196.493 Y222.417
G1 X191.327 Y227.583 E.22446
G1 X191.194 Y227.716
G1 X190.661 Y227.716
G1 X190.794 Y227.583
G1 X195.959 Y222.417 E.22446
G1 X196.093 Y222.284
G1 X195.56 Y222.284
G1 X195.426 Y222.417
G1 X190.261 Y227.583 E.22446
G1 X190.127 Y227.716
G1 X189.594 Y227.716
G1 X189.728 Y227.583
G1 X194.893 Y222.417 E.22446
G1 X195.027 Y222.284
G1 X194.493 Y222.284
G1 X194.36 Y222.417
G1 X189.194 Y227.583 E.22446
G1 X189.061 Y227.716
G1 X188.528 Y227.716
G1 X188.661 Y227.583
G1 X193.826 Y222.417 E.22446
G1 X193.96 Y222.284
G1 X193.427 Y222.284
G1 X193.293 Y222.417
G1 X188.128 Y227.583 E.22446
G1 X187.994 Y227.716
G1 X187.461 Y227.716
G1 X187.595 Y227.583
G1 X192.76 Y222.417 E.22446
G1 X192.894 Y222.284
G1 X192.36 Y222.284
G1 X192.227 Y222.417
G1 X187.061 Y227.583 E.22446
G1 X186.928 Y227.716
G1 X186.395 Y227.716
G1 X186.528 Y227.583
G1 X191.693 Y222.417 E.22446
G1 X191.827 Y222.284
G1 X191.294 Y222.284
G1 X191.16 Y222.417
G1 X185.995 Y227.583 E.22446
G1 X185.861 Y227.716
G1 X185.328 Y227.716
G1 X185.462 Y227.583
G1 X190.627 Y222.417 E.22446
G1 X190.761 Y222.284
G1 X190.227 Y222.284
G1 X190.094 Y222.417
G1 X184.928 Y227.583 E.22446
G1 X184.795 Y227.716
G1 X184.261 Y227.716
G1 X184.395 Y227.583
G1 X189.56 Y222.417 E.22446
G1 X189.694 Y222.284
G1 X189.161 Y222.284
G1 X189.027 Y222.417
G1 X183.862 Y227.583 E.22446
G1 X183.728 Y227.716
G1 X183.195 Y227.716
G1 X183.329 Y227.583
G1 X188.494 Y222.417 E.22446
G1 X188.627 Y222.284
G1 X188.094 Y222.284
G1 X187.961 Y222.417
G1 X182.795 Y227.583 E.22446
G1 X182.662 Y227.716
G1 X182.128 Y227.716
G1 X182.262 Y227.583
G1 X187.427 Y222.417 E.22446
G1 X187.561 Y222.284
G1 X187.028 Y222.284
G1 X186.894 Y222.417
G1 X181.729 Y227.583 E.22446
G1 X181.595 Y227.716
G1 X181.062 Y227.716
G1 X181.196 Y227.583
G1 X186.361 Y222.417 E.22445
G1 X186.494 Y222.284
G1 X185.961 Y222.284
G1 X185.828 Y222.417
G1 X180.662 Y227.583 E.22446
G1 X180.529 Y227.716
G1 X179.995 Y227.716
G1 X180.129 Y227.583
G1 X185.294 Y222.417 E.22446
G1 X185.428 Y222.284
G1 X184.895 Y222.284
G1 X184.761 Y222.417
G1 X179.596 Y227.583 E.22446
G1 X179.462 Y227.716
G1 X178.929 Y227.716
G1 X179.063 Y227.583
G1 X184.228 Y222.417 E.22445
G1 X184.361 Y222.284
G1 X183.828 Y222.284
G1 X183.695 Y222.417
G1 X178.529 Y227.583 E.22446
G1 X178.396 Y227.716
G1 X177.862 Y227.716
G1 X177.996 Y227.583
G1 X183.161 Y222.417 E.22446
G1 X183.295 Y222.284
G1 X182.762 Y222.284
G1 X182.628 Y222.417
G1 X177.463 Y227.583 E.22446
G1 X177.329 Y227.716
G1 X176.796 Y227.716
G1 X176.93 Y227.583
G1 X182.095 Y222.417 E.22445
G1 X182.228 Y222.284
G1 X181.695 Y222.284
G1 X181.562 Y222.417
G1 X176.396 Y227.583 E.22446
G1 X176.263 Y227.716
G1 X175.729 Y227.716
G1 X175.863 Y227.583
G1 X181.028 Y222.417 E.22446
G1 X181.162 Y222.284
G1 X180.629 Y222.284
G1 X180.495 Y222.417
G1 X175.33 Y227.583 E.22446
G1 X175.196 Y227.716
G1 X174.663 Y227.716
G1 X174.796 Y227.583
G1 X179.962 Y222.417 E.22445
G1 X180.095 Y222.284
G1 X179.562 Y222.284
G1 X179.428 Y222.417
G1 X174.263 Y227.583 E.22446
G1 X174.13 Y227.716
G1 X173.596 Y227.716
G1 X173.73 Y227.583
G1 X178.895 Y222.417 E.22446
G1 X179.029 Y222.284
G1 X178.496 Y222.284
G1 X178.362 Y222.417
G1 X173.197 Y227.583 E.22446
G1 X173.063 Y227.716
G1 X172.53 Y227.716
G1 X172.663 Y227.583
G1 X177.829 Y222.417 E.22445
G1 X177.962 Y222.284
G1 X177.429 Y222.284
G1 X177.295 Y222.417
G1 X172.13 Y227.583 E.22446
G1 X171.997 Y227.716
G1 X171.463 Y227.716
G1 X171.597 Y227.583
G1 X176.762 Y222.417 E.22446
G1 X176.896 Y222.284
G1 X176.363 Y222.284
G1 X176.229 Y222.417
G1 X171.064 Y227.583 E.22446
G1 X170.93 Y227.716
G1 X170.397 Y227.716
G1 X170.53 Y227.583
G1 X175.696 Y222.417 E.22445
G1 X175.829 Y222.284
G1 X175.296 Y222.284
G1 X175.162 Y222.417
G1 X169.997 Y227.583 E.22446
G1 X169.864 Y227.716
G1 X169.33 Y227.716
G1 X169.464 Y227.583
G1 X174.629 Y222.417 E.22446
G1 X174.763 Y222.284
G1 X174.23 Y222.284
G1 X174.096 Y222.417
G1 X168.931 Y227.583 E.22446
G1 X168.797 Y227.716
G1 X168.264 Y227.716
G1 X168.397 Y227.583
G1 X173.563 Y222.417 E.22445
G1 X173.696 Y222.284
G1 X173.163 Y222.284
G1 X173.029 Y222.417
G1 X167.864 Y227.583 E.22446
G1 X167.73 Y227.716
G1 X167.197 Y227.716
G1 X167.331 Y227.583
G1 X172.496 Y222.417 E.22446
G1 X172.63 Y222.284
G1 X172.097 Y222.284
G1 X171.963 Y222.417
G1 X166.798 Y227.583 E.22446
G1 X166.664 Y227.716
G1 X166.131 Y227.716
G1 X166.264 Y227.583
G1 X171.43 Y222.417 E.22445
G1 X171.563 Y222.284
G1 X171.03 Y222.284
G1 X170.896 Y222.417
G1 X165.731 Y227.583 E.22446
G1 X165.597 Y227.716
M73 P93 R1
G1 X165.064 Y227.716
G1 X165.198 Y227.583
G1 X170.363 Y222.417 E.22446
G1 X170.497 Y222.284
G1 X169.963 Y222.284
G1 X169.83 Y222.417
G1 X164.665 Y227.583 E.22445
G1 X164.531 Y227.716
G1 X163.998 Y227.716
G1 X164.131 Y227.583
G1 X169.297 Y222.417 E.22445
G1 X169.43 Y222.284
G1 X168.897 Y222.284
G1 X168.763 Y222.417
G1 X163.598 Y227.583 E.22445
G1 X163.464 Y227.716
G1 X162.931 Y227.716
G1 X163.065 Y227.583
G1 X168.23 Y222.417 E.22446
G1 X168.364 Y222.284
G1 X167.83 Y222.284
G1 X167.697 Y222.417
G1 X162.532 Y227.583 E.22446
G1 X162.398 Y227.716
G1 X161.865 Y227.716
G1 X161.998 Y227.583
G1 X167.164 Y222.417 E.22446
G1 X167.297 Y222.284
G1 X166.764 Y222.284
G1 X166.63 Y222.417
G1 X161.465 Y227.583 E.22446
G1 X161.331 Y227.716
G1 X160.798 Y227.716
G1 X160.932 Y227.583
G1 X166.097 Y222.417 E.22446
G1 X166.231 Y222.284
G1 X165.697 Y222.284
G1 X165.564 Y222.417
G1 X160.399 Y227.583 E.22446
G1 X160.265 Y227.716
G1 X159.732 Y227.716
G1 X159.865 Y227.583
G1 X165.031 Y222.417 E.22446
G1 X165.164 Y222.284
G1 X164.631 Y222.284
G1 X164.497 Y222.417
G1 X159.332 Y227.583 E.22446
G1 X159.198 Y227.716
G1 X158.665 Y227.716
G1 X158.799 Y227.583
G1 X163.964 Y222.417 E.22446
G1 X164.098 Y222.284
G1 X163.564 Y222.284
G1 X163.431 Y222.417
G1 X158.265 Y227.583 E.22446
G1 X158.132 Y227.716
G1 X157.599 Y227.716
G1 X157.732 Y227.583
G1 X162.897 Y222.417 E.22446
G1 X163.031 Y222.284
G1 X162.498 Y222.284
G1 X162.364 Y222.417
G1 X157.199 Y227.583 E.22446
G1 X157.065 Y227.716
G1 X156.532 Y227.716
G1 X156.666 Y227.583
G1 X161.831 Y222.417 E.22446
G1 X161.965 Y222.284
G1 X161.431 Y222.284
G1 X161.298 Y222.417
G1 X156.132 Y227.583 E.22446
G1 X155.999 Y227.716
G1 X155.466 Y227.716
G1 X155.599 Y227.583
G1 X160.764 Y222.417 E.22446
G1 X160.898 Y222.284
G1 X160.365 Y222.284
G1 X160.231 Y222.417
G1 X155.066 Y227.583 E.22446
G1 X154.932 Y227.716
G1 X154.399 Y227.716
G1 X154.533 Y227.583
G1 X159.698 Y222.417 E.22446
G1 X159.832 Y222.284
G1 X159.298 Y222.284
G1 X159.165 Y222.417
G1 X153.999 Y227.583 E.22446
G1 X153.866 Y227.716
G1 X153.333 Y227.716
G1 X153.466 Y227.583
G1 X158.631 Y222.417 E.22446
G1 X158.765 Y222.284
G1 X158.232 Y222.284
G1 X158.098 Y222.417
G1 X152.933 Y227.583 E.22446
G1 X152.799 Y227.716
G1 X152.266 Y227.716
G1 X152.4 Y227.583
G1 X157.565 Y222.417 E.22446
G1 X157.699 Y222.284
G1 X157.165 Y222.284
G1 X157.032 Y222.417
G1 X151.866 Y227.583 E.22446
G1 X151.733 Y227.716
G1 X151.2 Y227.716
G1 X151.333 Y227.583
G1 X156.498 Y222.417 E.22446
G1 X156.632 Y222.284
G1 X156.099 Y222.284
G1 X155.965 Y222.417
G1 X150.8 Y227.583 E.22446
G1 X150.666 Y227.716
G1 X150.133 Y227.716
G1 X150.267 Y227.583
G1 X155.432 Y222.417 E.22446
G1 X155.566 Y222.284
G1 X155.032 Y222.284
G1 X154.899 Y222.417
G1 X149.733 Y227.583 E.22446
G1 X149.6 Y227.716
G1 X149.066 Y227.716
G1 X149.2 Y227.583
G1 X154.365 Y222.417 E.22446
G1 X154.499 Y222.284
G1 X153.966 Y222.284
G1 X153.832 Y222.417
G1 X148.667 Y227.583 E.22446
G1 X148.533 Y227.716
G1 X148 Y227.716
G1 X148.134 Y227.583
G1 X153.299 Y222.417 E.22446
G1 X153.432 Y222.284
G1 X152.899 Y222.284
G1 X152.766 Y222.417
G1 X147.6 Y227.583 E.22446
G1 X147.467 Y227.716
G1 X146.933 Y227.716
G1 X147.067 Y227.583
G1 X152.232 Y222.417 E.22446
G1 X152.366 Y222.284
G1 X151.833 Y222.284
G1 X151.699 Y222.417
G1 X146.534 Y227.583 E.22446
G1 X146.4 Y227.716
G1 X145.867 Y227.716
G1 X146.001 Y227.583
G1 X151.166 Y222.417 E.22446
G1 X151.299 Y222.284
G1 X150.766 Y222.284
G1 X150.633 Y222.417
G1 X145.467 Y227.583 E.22446
G1 X145.334 Y227.716
G1 X144.8 Y227.716
G1 X144.934 Y227.583
G1 X150.099 Y222.417 E.22446
G1 X150.233 Y222.284
G1 X149.7 Y222.284
G1 X149.566 Y222.417
G1 X144.401 Y227.583 E.22446
G1 X144.267 Y227.716
G1 X143.734 Y227.716
G1 X143.868 Y227.583
G1 X149.033 Y222.417 E.22446
G1 X149.166 Y222.284
G1 X148.633 Y222.284
G1 X148.5 Y222.417
G1 X143.334 Y227.583 E.22446
G1 X143.201 Y227.716
G1 X142.667 Y227.716
G1 X142.801 Y227.583
G1 X147.966 Y222.417 E.22446
G1 X148.1 Y222.284
G1 X147.567 Y222.284
G1 X147.433 Y222.417
G1 X142.268 Y227.583 E.22446
G1 X142.134 Y227.716
G1 X141.601 Y227.716
G1 X141.735 Y227.583
G1 X146.9 Y222.417 E.22446
G1 X147.033 Y222.284
G1 X146.5 Y222.284
G1 X146.366 Y222.417
G1 X141.201 Y227.583 E.22445
G1 X141.068 Y227.716
G1 X140.534 Y227.716
G1 X140.668 Y227.583
G1 X145.833 Y222.417 E.22446
G1 X145.967 Y222.284
G1 X145.434 Y222.284
G1 X145.3 Y222.417
G1 X140.135 Y227.583 E.22446
G1 X140.001 Y227.716
G1 X139.468 Y227.716
G1 X139.601 Y227.583
G1 X144.767 Y222.417 E.22446
G1 X144.9 Y222.284
G1 X144.367 Y222.284
G1 X144.233 Y222.417
G1 X139.068 Y227.583 E.22445
G1 X138.935 Y227.716
G1 X138.401 Y227.716
G1 X138.535 Y227.583
G1 X143.7 Y222.417 E.22446
G1 X143.834 Y222.284
G1 X143.301 Y222.284
G1 X143.167 Y222.417
G1 X138.002 Y227.583 E.22446
G1 X137.868 Y227.716
G1 X137.335 Y227.716
G1 X137.468 Y227.583
G1 X142.634 Y222.417 E.22446
G1 X142.767 Y222.284
G1 X142.234 Y222.284
G1 X142.1 Y222.417
G1 X136.935 Y227.583 E.22445
G1 X136.802 Y227.716
G1 X136.268 Y227.716
G1 X136.402 Y227.583
G1 X141.567 Y222.417 E.22446
G1 X141.701 Y222.284
G1 X141.168 Y222.284
G1 X141.034 Y222.417
G1 X135.869 Y227.583 E.22446
G1 X135.735 Y227.716
G1 X135.202 Y227.716
G1 X135.335 Y227.583
G1 X140.501 Y222.417 E.22446
G1 X140.634 Y222.284
G1 X140.101 Y222.284
G1 X139.967 Y222.417
G1 X134.802 Y227.583 E.22445
G1 X134.669 Y227.716
G1 X134.135 Y227.716
G1 X134.269 Y227.583
G1 X139.434 Y222.417 E.22446
G1 X139.568 Y222.284
G1 X139.035 Y222.284
G1 X138.901 Y222.417
G1 X133.736 Y227.583 E.22446
G1 X133.602 Y227.716
G1 X133.069 Y227.716
G1 X133.202 Y227.583
G1 X138.368 Y222.417 E.22446
G1 X138.501 Y222.284
G1 X137.968 Y222.284
G1 X137.834 Y222.417
G1 X132.669 Y227.583 E.22445
G1 X132.535 Y227.716
G1 X132.002 Y227.716
G1 X132.136 Y227.583
G1 X137.301 Y222.417 E.22446
G1 X137.435 Y222.284
G1 X136.902 Y222.284
G1 X136.768 Y222.417
G1 X131.603 Y227.583 E.22446
G1 X131.469 Y227.716
G1 X130.936 Y227.716
G1 X131.069 Y227.583
G1 X136.235 Y222.417 E.22446
G1 X136.368 Y222.284
G1 X135.835 Y222.284
G1 X135.701 Y222.417
G1 X130.536 Y227.583 E.22445
G1 X130.402 Y227.716
G1 X129.869 Y227.716
G1 X130.003 Y227.583
G1 X135.168 Y222.417 E.22446
G1 X135.302 Y222.284
G1 X134.768 Y222.284
G1 X134.635 Y222.417
G1 X129.47 Y227.583 E.22446
G1 X129.336 Y227.716
G1 X128.803 Y227.716
G1 X128.936 Y227.583
G1 X134.102 Y222.417 E.22446
G1 X134.235 Y222.284
G1 X133.702 Y222.284
G1 X133.568 Y222.417
G1 X128.403 Y227.583 E.22445
G1 X128.269 Y227.716
G1 X127.736 Y227.716
G1 X127.87 Y227.583
G1 X133.035 Y222.417 E.22446
G1 X133.169 Y222.284
G1 X132.635 Y222.284
G1 X132.502 Y222.417
G1 X127.337 Y227.583 E.22446
G1 X127.203 Y227.716
G1 X126.67 Y227.716
G1 X126.803 Y227.583
G1 X131.969 Y222.417 E.22446
G1 X132.102 Y222.284
G1 X131.569 Y222.284
G1 X131.435 Y222.417
G1 X126.27 Y227.583 E.22446
G1 X126.136 Y227.716
G1 X125.603 Y227.716
G1 X125.737 Y227.583
G1 X130.902 Y222.417 E.22446
G1 X131.036 Y222.284
G1 X130.502 Y222.284
G1 X130.369 Y222.417
G1 X125.204 Y227.583 E.22446
G1 X125.07 Y227.716
G1 X124.537 Y227.716
G1 X124.67 Y227.583
G1 X129.836 Y222.417 E.22446
G1 X129.969 Y222.284
G1 X129.436 Y222.284
G1 X129.302 Y222.417
G1 X124.137 Y227.583 E.22446
G1 X124.003 Y227.716
G1 X123.47 Y227.716
G1 X123.604 Y227.583
G1 X128.769 Y222.417 E.22446
G1 X128.903 Y222.284
G1 X128.369 Y222.284
G1 X128.236 Y222.417
G1 X123.07 Y227.583 E.22446
G1 X122.937 Y227.716
G1 X122.404 Y227.716
G1 X122.537 Y227.583
G1 X127.702 Y222.417 E.22446
G1 X127.836 Y222.284
G1 X127.303 Y222.284
G1 X127.169 Y222.417
G1 X122.004 Y227.583 E.22446
G1 X121.87 Y227.716
G1 X121.337 Y227.716
G1 X121.471 Y227.583
G1 X126.636 Y222.417 E.22446
G1 X126.77 Y222.284
G1 X126.236 Y222.284
G1 X126.103 Y222.417
G1 X120.937 Y227.583 E.22446
G1 X120.804 Y227.716
G1 X120.271 Y227.716
G1 X120.404 Y227.583
G1 X125.569 Y222.417 E.22446
G1 X125.703 Y222.284
G1 X125.17 Y222.284
G1 X125.036 Y222.417
G1 X119.871 Y227.583 E.22446
G1 X119.737 Y227.716
G1 X119.204 Y227.716
G1 X119.338 Y227.583
G1 X124.503 Y222.417 E.22446
G1 X124.637 Y222.284
G1 X124.103 Y222.284
G1 X123.97 Y222.417
G1 X118.804 Y227.583 E.22446
G1 X118.671 Y227.716
G1 X118.138 Y227.716
G1 X118.271 Y227.583
G1 X123.436 Y222.417 E.22446
G1 X123.57 Y222.284
G1 X123.037 Y222.284
G1 X122.903 Y222.417
G1 X117.738 Y227.583 E.22446
G1 X117.604 Y227.716
G1 X117.071 Y227.716
G1 X117.205 Y227.583
G1 X122.37 Y222.417 E.22446
G1 X122.504 Y222.284
G1 X121.97 Y222.284
G1 X121.837 Y222.417
G1 X116.671 Y227.583 E.22446
G1 X116.538 Y227.716
G1 X116.005 Y227.716
G1 X116.138 Y227.583
G1 X121.303 Y222.417 E.22446
G1 X121.437 Y222.284
G1 X120.904 Y222.284
G1 X120.77 Y222.417
G1 X115.605 Y227.583 E.22446
G1 X115.471 Y227.716
G1 X114.938 Y227.716
G1 X115.072 Y227.583
G1 X120.237 Y222.417 E.22446
G1 X120.371 Y222.284
G1 X119.837 Y222.284
G1 X119.704 Y222.417
G1 X114.538 Y227.583 E.22446
G1 X114.405 Y227.716
G1 X113.871 Y227.716
G1 X114.005 Y227.583
G1 X119.17 Y222.417 E.22446
G1 X119.304 Y222.284
G1 X118.771 Y222.284
G1 X118.637 Y222.417
G1 X113.472 Y227.583 E.22446
G1 X113.338 Y227.716
G1 X112.805 Y227.716
G1 X112.939 Y227.583
G1 X118.104 Y222.417 E.22446
G1 X118.237 Y222.284
G1 X117.704 Y222.284
G1 X117.571 Y222.417
G1 X112.405 Y227.583 E.22446
G1 X112.272 Y227.716
G1 X111.738 Y227.716
G1 X111.872 Y227.583
G1 X117.037 Y222.417 E.22446
G1 X117.171 Y222.284
G1 X116.638 Y222.284
G1 X116.504 Y222.417
G1 X111.339 Y227.583 E.22446
G1 X111.205 Y227.716
G1 X110.672 Y227.716
G1 X110.806 Y227.583
G1 X115.971 Y222.417 E.22446
G1 X116.104 Y222.284
G1 X115.571 Y222.284
G1 X115.438 Y222.417
G1 X110.272 Y227.583 E.22446
G1 X110.139 Y227.716
G1 X109.605 Y227.716
G1 X109.739 Y227.583
G1 X114.904 Y222.417 E.22446
G1 X115.038 Y222.284
G1 X114.505 Y222.284
G1 X114.371 Y222.417
G1 X109.206 Y227.583 E.22446
G1 X109.072 Y227.716
G1 X108.539 Y227.716
G1 X108.673 Y227.583
G1 X113.838 Y222.417 E.22446
G1 X113.971 Y222.284
G1 X113.438 Y222.284
G1 X113.305 Y222.417
G1 X108.139 Y227.583 E.22446
G1 X108.006 Y227.716
G1 X107.472 Y227.716
G1 X107.606 Y227.583
G1 X112.771 Y222.417 E.22446
G1 X112.905 Y222.284
G1 X112.372 Y222.284
G1 X112.238 Y222.417
G1 X107.073 Y227.583 E.22446
G1 X106.939 Y227.716
G1 X106.406 Y227.716
G1 X106.54 Y227.583
G1 X111.705 Y222.417 E.22446
G1 X111.838 Y222.284
G1 X111.305 Y222.284
G1 X111.172 Y222.417
G1 X106.006 Y227.583 E.22446
G1 X105.873 Y227.716
G1 X105.339 Y227.716
G1 X105.473 Y227.583
G1 X110.638 Y222.417 E.22446
G1 X110.772 Y222.284
M73 P94 R1
G1 X110.239 Y222.284
G1 X110.105 Y222.417
G1 X104.94 Y227.583 E.22446
G1 X104.806 Y227.716
G1 X104.273 Y227.716
G1 X104.406 Y227.583
G1 X109.572 Y222.417 E.22446
G1 X109.705 Y222.284
G1 X109.172 Y222.284
G1 X109.038 Y222.417
G1 X103.873 Y227.583 E.22446
G1 X103.74 Y227.716
G1 X103.206 Y227.716
G1 X103.34 Y227.583
G1 X108.505 Y222.417 E.22446
G1 X108.639 Y222.284
G1 X108.106 Y222.284
G1 X107.972 Y222.417
G1 X102.807 Y227.583 E.22446
G1 X102.673 Y227.716
G1 X102.14 Y227.716
G1 X102.273 Y227.583
G1 X107.439 Y222.417 E.22446
G1 X107.572 Y222.284
G1 X107.039 Y222.284
G1 X106.905 Y222.417
G1 X101.74 Y227.583 E.22446
G1 X101.607 Y227.716
G1 X101.073 Y227.716
G1 X101.207 Y227.583
G1 X106.372 Y222.417 E.22445
G1 X106.506 Y222.284
G1 X105.973 Y222.284
G1 X105.839 Y222.417
G1 X100.674 Y227.583 E.22446
G1 X100.54 Y227.716
G1 X100.007 Y227.716
G1 X100.14 Y227.583
G1 X105.306 Y222.417 E.22446
G1 X105.439 Y222.284
G1 X104.906 Y222.284
G1 X104.772 Y222.417
G1 X99.607 Y227.583 E.22446
G1 X99.474 Y227.716
G1 X98.94 Y227.716
G1 X99.074 Y227.583
G1 X104.239 Y222.417 E.22445
G1 X104.373 Y222.284
G1 X103.84 Y222.284
G1 X103.706 Y222.417
G1 X98.541 Y227.583 E.22446
G1 X98.407 Y227.716
G1 X97.874 Y227.716
G1 X98.007 Y227.583
G1 X103.173 Y222.417 E.22446
G1 X103.306 Y222.284
G1 X102.773 Y222.284
G1 X102.639 Y222.417
G1 X97.474 Y227.583 E.22446
G1 X97.34 Y227.716
G1 X96.807 Y227.716
G1 X96.941 Y227.583
G1 X102.106 Y222.417 E.22445
G1 X102.24 Y222.284
G1 X101.707 Y222.284
G1 X101.573 Y222.417
G1 X96.408 Y227.583 E.22446
G1 X96.274 Y227.716
G1 X95.741 Y227.716
G1 X95.874 Y227.583
G1 X101.04 Y222.417 E.22446
G1 X101.173 Y222.284
G1 X100.64 Y222.284
G1 X100.506 Y222.417
G1 X95.341 Y227.583 E.22446
G1 X95.207 Y227.716
G1 X94.674 Y227.716
G1 X94.808 Y227.583
G1 X99.973 Y222.417 E.22445
G1 X100.107 Y222.284
G1 X99.573 Y222.284
G1 X99.44 Y222.417
G1 X94.275 Y227.583 E.22446
G1 X94.141 Y227.716
G1 X93.608 Y227.716
G1 X93.741 Y227.583
G1 X98.907 Y222.417 E.22446
G1 X99.04 Y222.284
G1 X98.507 Y222.284
G1 X98.373 Y222.417
G1 X93.208 Y227.583 E.22446
G1 X93.074 Y227.716
G1 X92.541 Y227.716
G1 X92.675 Y227.583
G1 X97.84 Y222.417 E.22445
G1 X97.974 Y222.284
G1 X97.44 Y222.284
G1 X97.307 Y222.417
G1 X92.142 Y227.583 E.22446
G1 X92.008 Y227.716
G1 X91.475 Y227.716
G1 X91.608 Y227.583
G1 X96.774 Y222.417 E.22446
G1 X96.907 Y222.284
G1 X96.374 Y222.284
G1 X96.24 Y222.417
G1 X91.075 Y227.583 E.22446
G1 X90.941 Y227.716
G1 X90.408 Y227.716
G1 X90.542 Y227.583
G1 X95.707 Y222.417 E.22446
G1 X95.841 Y222.284
G1 X95.307 Y222.284
G1 X95.174 Y222.417
G1 X90.009 Y227.583 E.22446
G1 X89.875 Y227.716
G1 X89.342 Y227.716
G1 X89.475 Y227.583
G1 X94.641 Y222.417 E.22446
G1 X94.774 Y222.284
G1 X94.241 Y222.284
G1 X94.107 Y222.417
G1 X88.942 Y227.583 E.22446
G1 X88.808 Y227.716
G1 X88.275 Y227.716
G1 X88.409 Y227.583
G1 X93.574 Y222.417 E.22446
G1 X93.708 Y222.284
G1 X93.174 Y222.284
G1 X93.041 Y222.417
G1 X87.875 Y227.583 E.22446
G1 X87.742 Y227.716
G1 X87.209 Y227.716
G1 X87.342 Y227.583
G1 X92.507 Y222.417 E.22446
G1 X92.641 Y222.284
G1 X92.108 Y222.284
G1 X91.974 Y222.417
G1 X86.809 Y227.583 E.22446
G1 X86.675 Y227.716
G1 X86.142 Y227.716
G1 X86.276 Y227.583
G1 X91.441 Y222.417 E.22446
G1 X91.575 Y222.284
G1 X91.041 Y222.284
G1 X90.908 Y222.417
G1 X85.742 Y227.583 E.22446
G1 X85.609 Y227.716
G1 X85.076 Y227.716
G1 X85.209 Y227.583
G1 X90.374 Y222.417 E.22446
G1 X90.508 Y222.284
G1 X89.975 Y222.284
G1 X89.841 Y222.417
G1 X84.676 Y227.583 E.22446
G1 X84.542 Y227.716
G1 X84.009 Y227.716
G1 X84.143 Y227.583
G1 X89.308 Y222.417 E.22446
G1 X89.442 Y222.284
G1 X88.908 Y222.284
G1 X88.775 Y222.417
G1 X83.609 Y227.583 E.22446
G1 X83.476 Y227.716
G1 X82.943 Y227.716
G1 X83.076 Y227.583
G1 X88.241 Y222.417 E.22446
G1 X88.375 Y222.284
G1 X87.842 Y222.284
G1 X87.708 Y222.417
G1 X82.543 Y227.583 E.22446
G1 X82.409 Y227.716
G1 X81.876 Y227.716
G1 X82.01 Y227.583
G1 X87.175 Y222.417 E.22446
G1 X87.309 Y222.284
G1 X86.775 Y222.284
G1 X86.642 Y222.417
G1 X81.476 Y227.583 E.22446
G1 X81.343 Y227.716
G1 X80.809 Y227.716
G1 X80.943 Y227.583
G1 X86.108 Y222.417 E.22446
G1 X86.242 Y222.284
G1 X85.709 Y222.284
G1 X85.575 Y222.417
G1 X80.41 Y227.583 E.22446
G1 X80.276 Y227.716
G1 X79.743 Y227.716
G1 X79.877 Y227.583
G1 X85.042 Y222.417 E.22446
G1 X85.176 Y222.284
G1 X84.642 Y222.284
G1 X84.509 Y222.417
G1 X79.343 Y227.583 E.22446
G1 X79.21 Y227.716
G1 X78.676 Y227.716
G1 X78.81 Y227.583
G1 X83.975 Y222.417 E.22446
G1 X84.109 Y222.284
G1 X83.576 Y222.284
G1 X83.442 Y222.417
G1 X78.277 Y227.583 E.22446
G1 X78.143 Y227.716
G1 X77.61 Y227.716
G1 X77.744 Y227.583
G1 X82.909 Y222.417 E.22446
G1 X83.042 Y222.284
G1 X82.509 Y222.284
G1 X82.376 Y222.417
G1 X77.21 Y227.583 E.22446
G1 X77.077 Y227.716
G1 X76.543 Y227.716
G1 X76.677 Y227.583
G1 X81.842 Y222.417 E.22446
G1 X81.976 Y222.284
G1 X81.443 Y222.284
G1 X81.309 Y222.417
G1 X76.144 Y227.583 E.22446
G1 X76.01 Y227.716
G1 X75.477 Y227.716
G1 X75.611 Y227.583
G1 X80.776 Y222.417 E.22446
G1 X80.909 Y222.284
G1 X80.376 Y222.284
G1 X80.243 Y222.417
G1 X75.077 Y227.583 E.22446
G1 X74.944 Y227.716
G1 X74.41 Y227.716
G1 X74.544 Y227.583
G1 X79.709 Y222.417 E.22446
G1 X79.843 Y222.284
G1 X79.31 Y222.284
G1 X79.176 Y222.417
G1 X74.011 Y227.583 E.22446
G1 X73.877 Y227.716
G1 X73.344 Y227.716
G1 X73.478 Y227.583
G1 X78.643 Y222.417 E.22446
G1 X78.776 Y222.284
G1 X78.243 Y222.284
G1 X78.11 Y222.417
G1 X72.944 Y227.583 E.22446
G1 X72.811 Y227.716
G1 X72.277 Y227.716
G1 X72.411 Y227.583
G1 X77.576 Y222.417 E.22446
G1 X77.71 Y222.284
G1 X77.177 Y222.284
G1 X77.043 Y222.417
G1 X71.878 Y227.583 E.22446
G1 X71.744 Y227.716
G1 X71.211 Y227.716
G1 X71.345 Y227.583
G1 X76.51 Y222.417 E.22446
G1 X76.643 Y222.284
G1 X76.11 Y222.284
G1 X75.976 Y222.417
G1 X70.811 Y227.583 E.22446
G1 X70.678 Y227.716
G1 X70.144 Y227.716
G1 X70.278 Y227.583
G1 X75.443 Y222.417 E.22446
G1 X75.577 Y222.284
G1 X75.044 Y222.284
G1 X74.91 Y222.417
G1 X69.745 Y227.583 E.22446
G1 X69.611 Y227.716
G1 X69.078 Y227.716
G1 X69.211 Y227.583
G1 X74.377 Y222.417 E.22446
G1 X74.51 Y222.284
G1 X73.977 Y222.284
G1 X73.843 Y222.417
G1 X68.678 Y227.583 E.22446
G1 X68.545 Y227.716
G1 X68.011 Y227.716
G1 X68.145 Y227.583
G1 X73.31 Y222.417 E.22446
G1 X73.444 Y222.284
G1 X72.911 Y222.284
G1 X72.777 Y222.417
G1 X67.612 Y227.583 E.22446
G1 X67.478 Y227.716
G1 X66.945 Y227.716
G1 X67.078 Y227.583
G1 X72.244 Y222.417 E.22446
G1 X72.377 Y222.284
G1 X71.844 Y222.284
G1 X71.71 Y222.417
G1 X66.545 Y227.583 E.22446
G1 X66.412 Y227.716
G1 X65.878 Y227.716
G1 X66.012 Y227.583
G1 X71.177 Y222.417 E.22446
G1 X71.311 Y222.284
G1 X70.778 Y222.284
G1 X70.644 Y222.417
G1 X65.479 Y227.583 E.22446
G1 X65.345 Y227.716
G1 X64.812 Y227.716
G1 X64.945 Y227.583
G1 X70.111 Y222.417 E.22446
G1 X70.244 Y222.284
G1 X69.711 Y222.284
G1 X69.577 Y222.417
G1 X64.412 Y227.583 E.22446
G1 X64.279 Y227.716
G1 X63.745 Y227.716
G1 X63.879 Y227.583
G1 X69.044 Y222.417 E.22446
G1 X69.178 Y222.284
G1 X68.645 Y222.284
G1 X68.511 Y222.417
G1 X63.346 Y227.583 E.22446
G1 X63.212 Y227.716
G1 X62.679 Y227.716
G1 X62.812 Y227.583
G1 X67.978 Y222.417 E.22446
G1 X68.111 Y222.284
G1 X67.578 Y222.284
G1 X67.444 Y222.417
G1 X62.279 Y227.583 E.22446
G1 X62.145 Y227.716
G1 X61.612 Y227.716
G1 X61.746 Y227.583
G1 X66.911 Y222.417 E.22446
G1 X67.045 Y222.284
G1 X66.511 Y222.284
G1 X66.378 Y222.417
G1 X61.213 Y227.583 E.22445
G1 X61.079 Y227.716
G1 X60.546 Y227.716
G1 X60.679 Y227.583
G1 X65.845 Y222.417 E.22446
G1 X65.978 Y222.284
G1 X65.445 Y222.284
G1 X65.311 Y222.417
G1 X60.146 Y227.583 E.22446
G1 X60.012 Y227.716
G1 X59.479 Y227.716
G1 X59.613 Y227.583
G1 X64.778 Y222.417 E.22446
G1 X64.912 Y222.284
G1 X64.378 Y222.284
G1 X64.245 Y222.417
G1 X59.08 Y227.583 E.22445
G1 X58.946 Y227.716
G1 X58.413 Y227.716
G1 X58.546 Y227.583
G1 X63.712 Y222.417 E.22445
G1 X63.845 Y222.284
G1 X63.312 Y222.284
G1 X63.178 Y222.417
G1 X58.013 Y227.583 E.22446
G1 X57.879 Y227.716
G1 X57.346 Y227.716
G1 X57.48 Y227.583
G1 X62.645 Y222.417 E.22446
G1 X62.779 Y222.284
G1 X62.245 Y222.284
G1 X62.112 Y222.417
G1 X56.947 Y227.583 E.22445
G1 X56.813 Y227.716
G1 X56.28 Y227.716
G1 X56.413 Y227.583
G1 X61.579 Y222.417 E.22446
G1 X61.712 Y222.284
G1 X61.179 Y222.284
G1 X61.045 Y222.417
G1 X55.88 Y227.583 E.22446
G1 X55.746 Y227.716
G1 X55.213 Y227.716
G1 X55.347 Y227.583
G1 X60.512 Y222.417 E.22446
G1 X60.646 Y222.284
G1 X60.112 Y222.284
G1 X59.979 Y222.417
G1 X54.814 Y227.583 E.22446
G1 X54.68 Y227.716
G1 X54.147 Y227.716
G1 X54.28 Y227.583
G1 X59.446 Y222.417 E.22446
G1 X59.579 Y222.284
G1 X59.046 Y222.284
G1 X58.912 Y222.417
G1 X53.747 Y227.583 E.22446
G1 X53.613 Y227.716
G1 X53.08 Y227.716
G1 X53.214 Y227.583
G1 X58.379 Y222.417 E.22446
G1 X58.513 Y222.284
G1 X57.979 Y222.284
G1 X57.846 Y222.417
G1 X52.68 Y227.583 E.22446
G1 X52.547 Y227.716
G1 X52.014 Y227.716
G1 X52.147 Y227.583
G1 X57.312 Y222.417 E.22446
G1 X57.446 Y222.284
G1 X56.913 Y222.284
G1 X56.779 Y222.417
G1 X51.614 Y227.583 E.22446
G1 X51.48 Y227.716
G1 X50.947 Y227.716
G1 X51.081 Y227.583
G1 X56.246 Y222.417 E.22446
G1 X56.38 Y222.284
G1 X55.846 Y222.284
G1 X55.713 Y222.417
G1 X50.547 Y227.583 E.22446
G1 X50.414 Y227.716
G1 X49.881 Y227.716
G1 X50.014 Y227.583
G1 X55.179 Y222.417 E.22446
G1 X55.313 Y222.284
G1 X54.78 Y222.284
G1 X54.646 Y222.417
G1 X49.481 Y227.583 E.22446
G1 X49.347 Y227.716
G1 X48.814 Y227.716
G1 X48.948 Y227.583
G1 X54.113 Y222.417 E.22446
G1 X54.247 Y222.284
G1 X53.713 Y222.284
G1 X53.58 Y222.417
G1 X48.414 Y227.583 E.22446
G1 X48.281 Y227.716
G1 X47.748 Y227.716
G1 X47.881 Y227.583
G1 X53.046 Y222.417 E.22446
G1 X53.18 Y222.284
G1 X52.647 Y222.284
G1 X52.513 Y222.417
G1 X47.348 Y227.583 E.22446
G1 X47.214 Y227.716
G1 X46.681 Y227.716
G1 X46.815 Y227.583
G1 X51.98 Y222.417 E.22446
G1 X52.114 Y222.284
G1 X51.58 Y222.284
G1 X51.447 Y222.417
G1 X46.281 Y227.583 E.22446
G1 X46.148 Y227.716
G1 X45.614 Y227.716
G1 X45.748 Y227.583
G1 X50.913 Y222.417 E.22446
G1 X51.047 Y222.284
G1 X50.514 Y222.284
G1 X50.38 Y222.417
G1 X45.215 Y227.583 E.22446
G1 X45.081 Y227.716
M73 P95 R1
G1 X44.548 Y227.716
G1 X44.682 Y227.583
G1 X49.847 Y222.417 E.22446
G1 X49.981 Y222.284
G1 X49.447 Y222.284
G1 X49.314 Y222.417
G1 X44.148 Y227.583 E.22446
G1 X44.015 Y227.716
G1 X43.481 Y227.716
G1 X43.615 Y227.583
G1 X48.78 Y222.417 E.22446
G1 X48.914 Y222.284
G1 X48.381 Y222.284
G1 X48.247 Y222.417
G1 X43.082 Y227.583 E.22446
G1 X42.948 Y227.716
G1 X42.415 Y227.716
G1 X42.549 Y227.583
G1 X47.714 Y222.417 E.22446
G1 X47.847 Y222.284
G1 X47.314 Y222.284
G1 X47.181 Y222.417
G1 X42.015 Y227.583 E.22446
G1 X41.882 Y227.716
G1 X41.348 Y227.716
G1 X41.482 Y227.583
G1 X46.647 Y222.417 E.22446
G1 X46.781 Y222.284
G1 X46.248 Y222.284
G1 X46.114 Y222.417
G1 X40.949 Y227.583 E.22446
G1 X40.815 Y227.716
G1 X40.282 Y227.716
G1 X40.416 Y227.583
G1 X45.581 Y222.417 E.22446
G1 X45.714 Y222.284
G1 X45.181 Y222.284
G1 X45.048 Y222.417
G1 X39.882 Y227.583 E.22446
G1 X39.749 Y227.716
G1 X39.215 Y227.716
G1 X39.349 Y227.583
G1 X44.514 Y222.417 E.22446
G1 X44.648 Y222.284
G1 X44.115 Y222.284
G1 X43.981 Y222.417
G1 X38.816 Y227.583 E.22446
G1 X38.682 Y227.716
G1 X38.149 Y227.716
G1 X38.283 Y227.583
G1 X43.448 Y222.417 E.22446
G1 X43.581 Y222.284
G1 X43.048 Y222.284
G1 X42.915 Y222.417
G1 X37.749 Y227.583 E.22446
G1 X37.616 Y227.716
G1 X37.082 Y227.716
G1 X37.216 Y227.583
G1 X42.381 Y222.417 E.22446
G1 X42.515 Y222.284
G1 X41.982 Y222.284
G1 X41.848 Y222.417
G1 X36.683 Y227.583 E.22446
G1 X36.549 Y227.716
G1 X36.016 Y227.716
G1 X36.15 Y227.583
G1 X41.315 Y222.417 E.22446
G1 X41.448 Y222.284
G1 X40.915 Y222.284
G1 X40.781 Y222.417
G1 X35.616 Y227.583 E.22446
G1 X35.483 Y227.716
G1 X34.949 Y227.716
G1 X35.083 Y227.583
G1 X40.248 Y222.417 E.22446
G1 X40.382 Y222.284
G1 X39.849 Y222.284
G1 X39.715 Y222.417
G1 X34.55 Y227.583 E.22446
G1 X34.416 Y227.716
G1 X33.883 Y227.716
G1 X34.016 Y227.583
G1 X39.182 Y222.417 E.22446
G1 X39.315 Y222.284
G1 X38.782 Y222.284
G1 X38.648 Y222.417
G1 X33.483 Y227.583 E.22446
G1 X33.35 Y227.716
G1 X32.816 Y227.716
G1 X32.95 Y227.583
G1 X38.115 Y222.417 E.22446
G1 X38.249 Y222.284
G1 X37.716 Y222.284
G1 X37.582 Y222.417
G1 X32.417 Y227.583 E.22446
G1 X32.283 Y227.716
G1 X31.75 Y227.716
G1 X31.883 Y227.583
G1 X37.049 Y222.417 E.22446
G1 X37.182 Y222.284
G1 X36.649 Y222.284
G1 X36.515 Y222.417
G1 X31.35 Y227.583 E.22446
G1 X31.217 Y227.716
G1 X30.683 Y227.716
G1 X30.817 Y227.583
G1 X35.982 Y222.417 E.22446
G1 X36.116 Y222.284
G1 X35.583 Y222.284
G1 X35.449 Y222.417
G1 X30.284 Y227.583 E.22446
G1 X30.15 Y227.716
G1 X29.617 Y227.716
G1 X29.75 Y227.583
G1 X34.916 Y222.417 E.22446
G1 X35.049 Y222.284
G1 X34.516 Y222.284
G1 X34.382 Y222.417
G1 X29.217 Y227.583 E.22446
G1 X29.084 Y227.716
G1 X28.55 Y227.716
G1 X28.684 Y227.583
G1 X33.849 Y222.417 E.22446
G1 X33.983 Y222.284
G1 X33.45 Y222.284
G1 X33.316 Y222.417
G1 X28.151 Y227.583 E.22446
G1 X28.017 Y227.716
G1 X27.484 Y227.716
G1 X27.617 Y227.583
G1 X32.783 Y222.417 E.22446
G1 X32.916 Y222.284
G1 X32.383 Y222.284
G1 X32.249 Y222.417
G1 X27.084 Y227.583 E.22446
G1 X26.95 Y227.716
G1 X26.417 Y227.716
G1 X26.551 Y227.583
G1 X31.716 Y222.417 E.22446
G1 X31.85 Y222.284
G1 X31.317 Y222.284
G1 X31.183 Y222.417
G1 X26.018 Y227.583 E.22446
G1 X25.884 Y227.716
G1 X25.351 Y227.716
G1 X25.484 Y227.583
G1 X30.65 Y222.417 E.22446
G1 X30.783 Y222.284
G1 X30.25 Y222.284
G1 X30.116 Y222.417
G1 X24.951 Y227.583 E.22446
G1 X24.817 Y227.716
G1 X24.284 Y227.716
G1 X24.418 Y227.583
G1 X29.583 Y222.417 E.22446
G1 X29.717 Y222.284
G1 X29.183 Y222.284
G1 X29.05 Y222.417
G1 X23.885 Y227.583 E.22446
G1 X23.751 Y227.716
G1 X23.218 Y227.716
G1 X23.351 Y227.583
G1 X28.517 Y222.417 E.22446
G1 X28.65 Y222.284
G1 X28.117 Y222.284
G1 X27.983 Y222.417
G1 X22.818 Y227.583 E.22445
G1 X22.684 Y227.716
G1 X22.151 Y227.716
G1 X22.285 Y227.583
G1 X27.45 Y222.417 E.22446
G1 X27.584 Y222.284
G1 X27.05 Y222.284
G1 X26.917 Y222.417
G1 X21.752 Y227.583 E.22446
G1 X21.618 Y227.716
G1 X21.085 Y227.716
G1 X21.218 Y227.583
G1 X26.384 Y222.417 E.22445
G1 X26.517 Y222.284
G1 X25.984 Y222.284
G1 X25.85 Y222.417
M73 P95 R0
G1 X20.685 Y227.583 E.22446
G1 X20.551 Y227.716
G1 X20.018 Y227.716
G1 X20.152 Y227.583
G1 X25.317 Y222.417 E.22446
G1 X25.451 Y222.284
G1 X24.917 Y222.284
G1 X24.784 Y222.417
G1 X19.619 Y227.583 E.22446
G1 X19.485 Y227.716
G1 X18.952 Y227.716
G1 X19.085 Y227.583
G1 X24.251 Y222.417 E.22446
G1 X24.384 Y222.284
G1 X23.851 Y222.284
G1 X23.717 Y222.417
G1 X18.552 Y227.583 E.22446
G1 X18.418 Y227.716
G1 X17.885 Y227.716
G1 X18.019 Y227.583
G1 X23.184 Y222.417 E.22446
G1 X23.318 Y222.284
G1 X22.784 Y222.284
G1 X22.651 Y222.417
G1 X17.485 Y227.583 E.22446
G1 X17.352 Y227.716
G1 X16.819 Y227.716
G1 X16.952 Y227.583
G1 X22.117 Y222.417 E.22446
G1 X22.251 Y222.284
G1 X21.718 Y222.284
G1 X21.584 Y222.417
G1 X16.419 Y227.583 E.22446
G1 X16.285 Y227.716
G1 X15.752 Y227.716
G1 X15.886 Y227.583
G1 X21.051 Y222.417 E.22446
G1 X21.185 Y222.284
G1 X20.651 Y222.284
G1 X20.518 Y222.417
G1 X15.352 Y227.583 E.22446
G1 X15.219 Y227.716
G1 X14.686 Y227.716
G1 X14.819 Y227.583
G1 X19.984 Y222.417 E.22446
G1 X20.118 Y222.284
G1 X19.585 Y222.284
G1 X19.451 Y222.417
G1 X14.286 Y227.583 E.22446
G1 X14.152 Y227.716
G1 X13.619 Y227.716
G1 X13.753 Y227.583
G1 X18.918 Y222.417 E.22446
G1 X19.052 Y222.284
G1 X18.518 Y222.284
G1 X18.385 Y222.417
G1 X13.219 Y227.583 E.22446
G1 X13.086 Y227.716
G1 X12.553 Y227.716
G1 X12.686 Y227.583
G1 X17.851 Y222.417 E.22446
G1 X17.985 Y222.284
G1 X17.452 Y222.284
G1 X17.318 Y222.417
G1 X12.153 Y227.583 E.22446
G1 X12.019 Y227.716
G1 X11.486 Y227.716
G1 X11.62 Y227.583
G1 X16.785 Y222.417 E.22446
G1 X16.919 Y222.284
G1 X16.385 Y222.284
G1 X16.252 Y222.417
G1 X11.086 Y227.583 E.22446
G1 X10.953 Y227.716
G1 X10.419 Y227.716
G1 X10.553 Y227.583
G1 X15.718 Y222.417 E.22446
G1 X15.852 Y222.284
G1 X15.319 Y222.284
G1 X15.185 Y222.417
G1 X10.02 Y227.583 E.22446
G1 X9.886 Y227.716
G1 X9.353 Y227.716
G1 X9.487 Y227.583
G1 X14.652 Y222.417 E.22446
G1 X14.786 Y222.284
G1 X14.252 Y222.284
G1 X14.119 Y222.417
G1 X8.953 Y227.583 E.22446
G1 X8.82 Y227.716
G1 X8.286 Y227.716
G1 X8.42 Y227.583
G1 X13.585 Y222.417 E.22446
G1 X13.719 Y222.284
G1 X13.186 Y222.284
G1 X13.052 Y222.417
G1 X7.887 Y227.583 E.22446
G1 X7.753 Y227.716
G1 X7.22 Y227.716
G1 X7.354 Y227.583
G1 X12.519 Y222.417 E.22446
G1 X12.652 Y222.284
G1 X12.119 Y222.284
G1 X11.986 Y222.417
G1 X6.82 Y227.583 E.22446
G1 X6.687 Y227.716
G1 X6.153 Y227.716
G1 X6.287 Y227.583
G1 X11.452 Y222.417 E.22446
G1 X11.586 Y222.284
G1 X11.053 Y222.284
G1 X10.919 Y222.417
G1 X5.754 Y227.583 E.22446
G1 X5.62 Y227.716
G1 X5.087 Y227.716
G1 X5.221 Y227.583
G1 X10.386 Y222.417 E.22446
G1 X10.519 Y222.284
G1 X9.986 Y222.284
G1 X9.853 Y222.417
G1 X4.687 Y227.583 E.22446
G1 X4.554 Y227.716
G1 X4.02 Y227.716
G1 X4.154 Y227.583
G1 X9.319 Y222.417 E.22446
G1 X9.453 Y222.284
G1 X8.92 Y222.284
G1 X8.786 Y222.417
G1 X3.621 Y227.583 E.22446
G1 X3.487 Y227.716
G1 X3.284 Y227.386
G1 X3.417 Y227.253
G1 X8.583 Y222.088 E.22446
G1 X8.716 Y221.954
G1 X8.716 Y221.421
G1 X8.583 Y221.554
G1 X3.417 Y226.72 E.22446
G1 X3.284 Y226.853
G1 X3.284 Y226.32
G1 X3.417 Y226.186
G1 X8.583 Y221.021 E.22446
G1 X8.716 Y220.887
G1 X8.716 Y220.354
G1 X8.583 Y220.488
G1 X3.417 Y225.653 E.22446
G1 X3.284 Y225.787
G1 X3.284 Y225.253
G1 X3.417 Y225.12
G1 X8.583 Y219.955 E.22446
G1 X8.716 Y219.821
G1 X8.716 Y219.288
G1 X8.583 Y219.421
G1 X3.417 Y224.587 E.22446
G1 X3.284 Y224.72
G1 X3.284 Y224.187
G1 X3.417 Y224.053
G1 X8.583 Y218.888 E.22446
G1 X8.716 Y218.754
G1 X8.716 Y218.221
G1 X8.583 Y218.355
G1 X3.417 Y223.52 E.22446
G1 X3.284 Y223.654
G1 X3.284 Y223.12
G1 X3.417 Y222.987
G1 X8.583 Y217.821 E.22446
G1 X8.716 Y217.688
G1 X8.716 Y217.155
G1 X8.583 Y217.288
G1 X3.417 Y222.453 E.22446
G1 X3.284 Y222.587
G1 X3.284 Y222.054
G1 X3.417 Y221.92
G1 X8.583 Y216.755 E.22446
G1 X8.716 Y216.621
G1 X8.716 Y216.088
G1 X8.583 Y216.222
G1 X3.417 Y221.387 E.22446
G1 X3.284 Y221.521
G1 X3.284 Y220.987
G1 X3.417 Y220.854
G1 X8.583 Y215.688 E.22446
G1 X8.716 Y215.555
G1 X8.716 Y215.022
G1 X8.583 Y215.155
G1 X3.417 Y220.32 E.22446
G1 X3.284 Y220.454
G1 X3.284 Y219.921
G1 X3.417 Y219.787
G1 X8.583 Y214.622 E.22446
G1 X8.716 Y214.488
G1 X8.716 Y213.955
G1 X8.583 Y214.089
G1 X3.417 Y219.254 E.22446
G1 X3.284 Y219.388
G1 X3.284 Y218.854
G1 X3.417 Y218.721
G1 X8.583 Y213.555 E.22446
G1 X8.716 Y213.422
G1 X8.716 Y212.889
G1 X8.583 Y213.022
G1 X3.417 Y218.187 E.22446
G1 X3.284 Y218.321
G1 X3.284 Y217.788
G1 X3.417 Y217.654
G1 X8.583 Y212.489 E.22446
G1 X8.716 Y212.355
G1 X8.716 Y211.822
G1 X8.583 Y211.956
G1 X3.417 Y217.121 E.22446
G1 X3.284 Y217.255
G1 X3.284 Y216.721
G1 X3.417 Y216.588
G1 X8.583 Y211.422 E.22446
G1 X8.716 Y211.289
G1 X8.716 Y210.755
G1 X8.583 Y210.889
G1 X3.417 Y216.054 E.22446
G1 X3.284 Y216.188
G1 X3.284 Y215.655
G1 X3.417 Y215.521
G1 X8.583 Y210.356 E.22446
G1 X8.716 Y210.222
G1 X8.716 Y209.689
G1 X8.583 Y209.823
G1 X3.417 Y214.988 E.22446
G1 X3.284 Y215.122
G1 X3.284 Y214.588
G1 X3.417 Y214.455
G1 X8.583 Y209.289 E.22446
G1 X8.716 Y209.156
G1 X8.716 Y208.622
G1 X8.583 Y208.756
G1 X3.417 Y213.921 E.22446
G1 X3.284 Y214.055
G1 X3.284 Y213.522
G1 X3.417 Y213.388
G1 X8.583 Y208.223 E.22446
G1 X8.716 Y208.089
G1 X8.716 Y207.556
G1 X8.583 Y207.69
G1 X3.417 Y212.855 E.22446
G1 X3.284 Y212.988
G1 X3.284 Y212.455
G1 X3.417 Y212.322
G1 X8.583 Y207.156 E.22446
G1 X8.716 Y207.023
G1 X8.716 Y206.489
G1 X8.583 Y206.623
G1 X3.417 Y211.788 E.22446
G1 X3.284 Y211.922
G1 X3.284 Y211.389
G1 X3.417 Y211.255
G1 X8.583 Y206.09 E.22445
G1 X8.716 Y205.956
G1 X8.716 Y205.423
G1 X8.583 Y205.557
G1 X3.417 Y210.722 E.22445
G1 X3.284 Y210.855
G1 X3.284 Y210.322
G1 X3.417 Y210.189
G1 X8.583 Y205.023 E.22446
G1 X8.716 Y204.89
G1 X8.716 Y204.356
G1 X8.583 Y204.49
G1 X3.417 Y209.655 E.22446
G1 X3.284 Y209.789
G1 X3.284 Y209.256
G1 X3.417 Y209.122
G1 X8.583 Y203.957 E.22445
G1 X8.716 Y203.823
M73 P96 R0
G1 X8.716 Y203.29
G1 X8.583 Y203.424
G1 X3.417 Y208.589 E.22445
G1 X3.284 Y208.722
G1 X3.284 Y208.189
G1 X3.417 Y208.056
G1 X8.583 Y202.89 E.22446
G1 X8.716 Y202.757
G1 X8.716 Y202.223
G1 X8.583 Y202.357
G1 X3.417 Y207.522 E.22446
G1 X3.284 Y207.656
G1 X3.284 Y207.123
G1 X3.417 Y206.989
G1 X8.583 Y201.824 E.22446
G1 X8.716 Y201.69
G1 X8.716 Y201.157
G1 X8.583 Y201.291
G1 X3.417 Y206.456 E.22446
G1 X3.284 Y206.589
G1 X3.284 Y206.056
G1 X3.417 Y205.922
G1 X8.583 Y200.757 E.22446
G1 X8.716 Y200.624
G1 X8.716 Y200.09
G1 X8.583 Y200.224
G1 X3.417 Y205.389 E.22446
G1 X3.284 Y205.523
G1 X3.284 Y204.99
G1 X3.417 Y204.856
G1 X8.583 Y199.691 E.22446
G1 X8.716 Y199.557
G1 X8.716 Y199.024
G1 X8.583 Y199.157
G1 X3.417 Y204.323 E.22446
G1 X3.284 Y204.456
G1 X3.284 Y203.923
G1 X3.417 Y203.789
G1 X8.583 Y198.624 E.22446
G1 X8.716 Y198.491
G1 X8.716 Y197.957
G1 X8.583 Y198.091
G1 X3.417 Y203.256 E.22446
G1 X3.284 Y203.39
G1 X3.284 Y202.857
G1 X3.417 Y202.723
G1 X8.583 Y197.558 E.22446
G1 X8.716 Y197.424
G1 X8.716 Y196.891
G1 X8.583 Y197.024
G1 X3.417 Y202.19 E.22446
G1 X3.284 Y202.323
G1 X3.284 Y201.79
G1 X3.417 Y201.656
G1 X8.583 Y196.491 E.22446
G1 X8.716 Y196.358
G1 X8.716 Y195.824
G1 X8.583 Y195.958
G1 X3.417 Y201.123 E.22446
G1 X3.284 Y201.257
G1 X3.284 Y200.724
G1 X3.417 Y200.59
G1 X8.583 Y195.425 E.22446
G1 X8.716 Y195.291
G1 X8.716 Y194.758
G1 X8.583 Y194.891
G1 X3.417 Y200.057 E.22446
G1 X3.284 Y200.19
G1 X3.284 Y199.657
G1 X3.417 Y199.523
G1 X8.583 Y194.358 E.22446
G1 X8.716 Y194.225
G1 X8.716 Y193.691
G1 X8.583 Y193.825
G1 X3.417 Y198.99 E.22446
G1 X3.284 Y199.124
G1 X3.284 Y198.591
G1 X3.417 Y198.457
G1 X8.583 Y193.292 E.22446
G1 X8.716 Y193.158
G1 X8.716 Y192.625
G1 X8.583 Y192.758
G1 X3.417 Y197.924 E.22446
G1 X3.284 Y198.057
G1 X3.284 Y197.524
G1 X3.417 Y197.39
G1 X8.583 Y192.225 E.22446
G1 X8.716 Y192.091
G1 X8.716 Y191.558
G1 X8.583 Y191.692
G1 X3.417 Y196.857 E.22446
G1 X3.284 Y196.991
G1 X3.284 Y196.458
G1 X3.417 Y196.324
G1 X8.583 Y191.159 E.22446
G1 X8.716 Y191.025
G1 X8.716 Y190.492
G1 X8.583 Y190.625
G1 X3.417 Y195.791 E.22446
G1 X3.284 Y195.924
G1 X3.284 Y195.391
G1 X3.417 Y195.257
G1 X8.583 Y190.092 E.22446
G1 X8.716 Y189.958
G1 X8.716 Y189.425
G1 X8.583 Y189.559
G1 X3.417 Y194.724 E.22446
G1 X3.284 Y194.858
G1 X3.284 Y194.324
G1 X3.417 Y194.191
G1 X8.583 Y189.026 E.22446
G1 X8.716 Y188.892
G1 X8.716 Y188.359
G1 X8.583 Y188.492
G1 X3.417 Y193.658 E.22446
G1 X3.284 Y193.791
G1 X3.284 Y193.258
G1 X3.417 Y193.124
G1 X8.583 Y187.959 E.22446
G1 X8.716 Y187.825
G1 X8.716 Y187.292
G1 X8.583 Y187.426
G1 X3.417 Y192.591 E.22446
G1 X3.284 Y192.725
G1 X3.284 Y192.191
G1 X3.417 Y192.058
G1 X8.583 Y186.893 E.22446
G1 X8.716 Y186.759
G1 X8.716 Y186.226
G1 X8.583 Y186.359
G1 X3.417 Y191.525 E.22446
G1 X3.284 Y191.658
G1 X3.284 Y191.125
G1 X3.417 Y190.991
G1 X8.583 Y185.826 E.22446
G1 X8.716 Y185.692
G1 X8.716 Y185.159
G1 X8.583 Y185.293
G1 X3.417 Y190.458 E.22446
G1 X3.284 Y190.592
G1 X3.284 Y190.058
G1 X3.417 Y189.925
G1 X8.583 Y184.76 E.22446
G1 X8.716 Y184.626
G1 X8.716 Y184.093
G1 X8.583 Y184.226
G1 X3.417 Y189.392 E.22446
G1 X3.284 Y189.525
G1 X3.284 Y188.992
G1 X3.417 Y188.858
G1 X8.583 Y183.693 E.22446
G1 X8.716 Y183.559
G1 X8.716 Y183.026
G1 X8.583 Y183.16
G1 X3.417 Y188.325 E.22446
G1 X3.284 Y188.459
G1 X3.284 Y187.925
G1 X3.417 Y187.792
G1 X8.583 Y182.626 E.22446
G1 X8.716 Y182.493
G1 X8.716 Y181.96
G1 X8.583 Y182.093
G1 X3.417 Y187.258 E.22446
G1 X3.284 Y187.392
G1 X3.284 Y186.859
G1 X3.417 Y186.725
G1 X8.583 Y181.56 E.22446
G1 X8.716 Y181.426
G1 X8.716 Y180.893
G1 X8.583 Y181.027
G1 X3.417 Y186.192 E.22446
G1 X3.284 Y186.326
G1 X3.284 Y185.792
G1 X3.417 Y185.659
G1 X8.583 Y180.493 E.22446
G1 X8.716 Y180.36
G1 X8.716 Y179.827
G1 X8.583 Y179.96
G1 X3.417 Y185.125 E.22446
G1 X3.284 Y185.259
G1 X3.284 Y184.726
G1 X3.417 Y184.592
G1 X8.583 Y179.427 E.22446
G1 X8.716 Y179.293
G1 X8.716 Y178.76
G1 X8.583 Y178.894
G1 X3.417 Y184.059 E.22446
G1 X3.284 Y184.193
G1 X3.284 Y183.659
G1 X3.417 Y183.526
G1 X8.583 Y178.36 E.22446
G1 X8.716 Y178.227
G1 X8.716 Y177.694
G1 X8.583 Y177.827
G1 X3.417 Y182.992 E.22446
G1 X3.284 Y183.126
G1 X3.284 Y182.593
G1 X3.417 Y182.459
G1 X8.583 Y177.294 E.22446
G1 X8.716 Y177.16
G1 X8.716 Y176.627
G1 X8.583 Y176.761
G1 X3.417 Y181.926 E.22446
G1 X3.284 Y182.06
G1 X3.284 Y181.526
G1 X3.417 Y181.393
G1 X8.583 Y176.227 E.22446
G1 X8.716 Y176.094
G1 X8.716 Y175.561
G1 X8.583 Y175.694
G1 X3.417 Y180.859 E.22446
G1 X3.284 Y180.993
G1 X3.284 Y180.46
G1 X3.417 Y180.326
G1 X8.583 Y175.161 E.22445
G1 X8.716 Y175.027
G1 X8.716 Y174.494
G1 X8.583 Y174.628
G1 X3.417 Y179.793 E.22445
G1 X3.284 Y179.927
G1 X3.284 Y179.393
G1 X3.417 Y179.26
G1 X8.583 Y174.094 E.22446
G1 X8.716 Y173.961
G1 X8.716 Y173.427
G1 X8.583 Y173.561
G1 X3.417 Y178.726 E.22445
G1 X3.284 Y178.86
G1 X3.284 Y178.327
G1 X3.417 Y178.193
G1 X8.583 Y173.028 E.22445
G1 X8.716 Y172.894
G1 X8.716 Y172.361
G1 X8.583 Y172.495
G1 X3.417 Y177.66 E.22445
G1 X3.284 Y177.793
G1 X3.284 Y177.26
G1 X3.417 Y177.127
G1 X8.583 Y171.961 E.22446
G1 X8.716 Y171.828
G1 X8.716 Y171.294
G1 X8.583 Y171.428
G1 X3.417 Y176.593 E.22445
G1 X3.284 Y176.727
G1 X3.284 Y176.194
G1 X3.417 Y176.06
G1 X8.583 Y170.895 E.22445
G1 X8.716 Y170.761
G1 X8.716 Y170.228
G1 X8.583 Y170.362
G1 X3.417 Y175.527 E.22445
G1 X3.284 Y175.66
G1 X3.284 Y175.127
G1 X3.417 Y174.994
G1 X8.583 Y169.828 E.22446
G1 X8.716 Y169.695
G1 X8.716 Y169.161
G1 X8.583 Y169.295
G1 X3.417 Y174.46 E.22445
G1 X3.284 Y174.594
G1 X3.284 Y174.061
G1 X3.417 Y173.927
G1 X8.583 Y168.762 E.22445
G1 X8.716 Y168.628
G1 X8.716 Y168.095
G1 X8.583 Y168.229
G1 X3.417 Y173.394 E.22445
G1 X3.284 Y173.527
G1 X3.284 Y172.994
G1 X3.417 Y172.861
G1 X8.583 Y167.695 E.22446
G1 X8.716 Y167.562
G1 X8.716 Y167.028
G1 X8.583 Y167.162
G1 X3.417 Y172.327 E.22445
G1 X3.284 Y172.461
G1 X3.284 Y171.928
G1 X3.417 Y171.794
G1 X8.583 Y166.629 E.22445
G1 X8.716 Y166.495
G1 X8.716 Y165.962
G1 X8.583 Y166.096
G1 X3.417 Y171.261 E.22445
G1 X3.284 Y171.394
G1 X3.284 Y170.861
G1 X3.417 Y170.728
G1 X8.583 Y165.562 E.22446
G1 X8.716 Y165.429
G1 X8.716 Y164.895
G1 X8.583 Y165.029
G1 X3.417 Y170.194 E.22445
G1 X3.284 Y170.328
G1 X3.284 Y169.795
G1 X3.417 Y169.661
G1 X8.583 Y164.496 E.22445
G1 X8.716 Y164.362
G1 X8.716 Y163.829
G1 X8.583 Y163.962
G1 X3.417 Y169.128 E.22445
G1 X3.284 Y169.261
G1 X3.284 Y168.728
G1 X3.417 Y168.594
G1 X8.583 Y163.429 E.22446
G1 X8.716 Y163.296
G1 X8.716 Y162.762
G1 X8.583 Y162.896
G1 X3.417 Y168.061 E.22445
G1 X3.284 Y168.195
G1 X3.284 Y167.662
G1 X3.417 Y167.528
G1 X8.583 Y162.363 E.22446
G1 X8.716 Y162.229
G1 X8.716 Y161.696
G1 X8.583 Y161.829
G1 X3.417 Y166.995 E.22446
G1 X3.284 Y167.128
G1 X3.284 Y166.595
G1 X3.417 Y166.461
G1 X8.583 Y161.296 E.22446
G1 X8.716 Y161.163
G1 X8.716 Y160.629
G1 X8.583 Y160.763
G1 X3.417 Y165.928 E.22446
G1 X3.284 Y166.062
G1 X3.284 Y165.529
G1 X3.417 Y165.395
G1 X8.583 Y160.23 E.22446
G1 X8.716 Y160.096
G1 X8.716 Y159.563
G1 X8.583 Y159.696
G1 X3.417 Y164.862 E.22446
G1 X3.284 Y164.995
G1 X3.284 Y164.462
G1 X3.417 Y164.328
G1 X8.583 Y159.163 E.22446
G1 X8.716 Y159.03
G1 X8.716 Y158.496
G1 X8.583 Y158.63
G1 X3.417 Y163.795 E.22446
G1 X3.284 Y163.929
G1 X3.284 Y163.396
G1 X3.417 Y163.262
G1 X8.583 Y158.097 E.22446
G1 X8.716 Y157.963
G1 X8.716 Y157.43
G1 X8.583 Y157.563
G1 X3.417 Y162.729 E.22446
G1 X3.284 Y162.862
G1 X3.284 Y162.329
G1 X3.417 Y162.195
G1 X8.583 Y157.03 E.22446
G1 X8.716 Y156.896
G1 X8.716 Y156.363
G1 X8.583 Y156.497
G1 X3.417 Y161.662 E.22446
G1 X3.284 Y161.796
G1 X3.284 Y161.263
G1 X3.417 Y161.129
G1 X8.583 Y155.964 E.22446
G1 X8.716 Y155.83
G1 X8.716 Y155.297
G1 X8.583 Y155.43
G1 X3.417 Y160.596 E.22446
G1 X3.284 Y160.729
G1 X3.284 Y160.196
G1 X3.417 Y160.062
G1 X8.583 Y154.897 E.22446
G1 X8.716 Y154.763
G1 X8.716 Y154.23
G1 X8.583 Y154.364
G1 X3.417 Y159.529 E.22446
G1 X3.284 Y159.663
G1 X3.284 Y159.129
G1 X3.417 Y158.996
G1 X8.583 Y153.831 E.22446
G1 X8.716 Y153.697
G1 X8.716 Y153.164
G1 X8.583 Y153.297
G1 X3.417 Y158.463 E.22446
G1 X3.284 Y158.596
G1 X3.284 Y158.063
G1 X3.417 Y157.929
G1 X8.583 Y152.764 E.22446
G1 X8.716 Y152.63
G1 X8.716 Y152.097
G1 X8.583 Y152.231
G1 X3.417 Y157.396 E.22446
G1 X3.284 Y157.53
G1 X3.284 Y156.996
G1 X3.417 Y156.863
G1 X8.583 Y151.698 E.22446
G1 X8.716 Y151.564
G1 X8.716 Y151.031
G1 X8.583 Y151.164
G1 X3.417 Y156.33 E.22446
G1 X3.284 Y156.463
G1 X3.284 Y155.93
G1 X3.417 Y155.796
G1 X8.583 Y150.631 E.22446
G1 X8.716 Y150.497
G1 X8.716 Y149.964
G1 X8.583 Y150.098
G1 X3.417 Y155.263 E.22446
G1 X3.284 Y155.397
G1 X3.284 Y154.863
G1 X3.417 Y154.73
G1 X8.583 Y149.565 E.22446
G1 X8.716 Y149.431
G1 X8.716 Y148.898
G1 X8.583 Y149.031
G1 X3.417 Y154.197 E.22446
G1 X3.284 Y154.33
G1 X3.284 Y153.797
G1 X3.417 Y153.663
G1 X8.583 Y148.498 E.22446
G1 X8.716 Y148.364
G1 X8.716 Y147.831
G1 X8.583 Y147.965
G1 X3.417 Y153.13 E.22446
G1 X3.284 Y153.264
G1 X3.284 Y152.73
G1 X3.417 Y152.597
G1 X8.583 Y147.432 E.22446
G1 X8.716 Y147.298
G1 X8.716 Y146.765
G1 X8.583 Y146.898
G1 X3.417 Y152.063 E.22446
G1 X3.284 Y152.197
G1 X3.284 Y151.664
G1 X3.417 Y151.53
G1 X8.583 Y146.365 E.22446
G1 X8.716 Y146.231
G1 X8.716 Y145.698
G1 X8.583 Y145.832
G1 X3.417 Y150.997 E.22446
G1 X3.284 Y151.131
G1 X3.284 Y150.597
G1 X3.417 Y150.464
G1 X8.583 Y145.298 E.22446
G1 X8.716 Y145.165
G1 X8.716 Y144.632
G1 X8.583 Y144.765
G1 X3.417 Y149.93 E.22446
G1 X3.284 Y150.064
G1 X3.284 Y149.531
G1 X3.417 Y149.397
G1 X8.583 Y144.232 E.22446
G1 X8.716 Y144.098
G1 X8.716 Y143.565
G1 X8.583 Y143.699
G1 X3.417 Y148.864 E.22446
G1 X3.284 Y148.998
G1 X3.284 Y148.464
G1 X3.417 Y148.331
M73 P97 R0
G1 X8.583 Y143.165 E.22446
G1 X8.716 Y143.032
G1 X8.716 Y142.499
G1 X8.583 Y142.632
G1 X3.417 Y147.797 E.22445
G1 X3.284 Y147.931
G1 X3.284 Y147.398
G1 X3.417 Y147.264
G1 X8.583 Y142.099 E.22445
G1 X8.716 Y141.965
G1 X8.716 Y141.432
G1 X8.583 Y141.566
G1 X3.417 Y146.731 E.22446
G1 X3.284 Y146.865
G1 X3.284 Y146.331
G1 X3.417 Y146.198
G1 X8.583 Y141.032 E.22446
G1 X8.716 Y140.899
G1 X8.716 Y140.366
G1 X8.583 Y140.499
G1 X3.417 Y145.664 E.22445
G1 X3.284 Y145.798
G1 X3.284 Y145.265
G1 X3.417 Y145.131
G1 X8.583 Y139.966 E.22445
G1 X8.716 Y139.832
G1 X8.716 Y139.299
G1 X8.583 Y139.433
G1 X3.417 Y144.598 E.22446
G1 X3.284 Y144.732
G1 X3.284 Y144.198
G1 X3.417 Y144.065
G1 X8.583 Y138.899 E.22446
G1 X8.716 Y138.766
G1 X8.716 Y138.232
G1 X8.583 Y138.366
G1 X3.417 Y143.531 E.22445
G1 X3.284 Y143.665
G1 X3.284 Y143.132
G1 X3.417 Y142.998
G1 X8.583 Y137.833 E.22445
G1 X8.716 Y137.699
G1 X8.716 Y137.166
G1 X8.583 Y137.3
G1 X3.417 Y142.465 E.22446
G1 X3.284 Y142.599
G1 X3.284 Y142.065
G1 X3.417 Y141.932
G1 X8.583 Y136.766 E.22446
G1 X8.716 Y136.633
G1 X8.716 Y136.099
G1 X8.583 Y136.233
G1 X3.417 Y141.398 E.22445
G1 X3.284 Y141.532
G1 X3.284 Y140.999
G1 X3.417 Y140.865
G1 X8.583 Y135.7 E.22445
G1 X8.716 Y135.566
G1 X8.716 Y135.033
G1 X8.583 Y135.167
G1 X3.417 Y140.332 E.22446
G1 X3.284 Y140.465
G1 X3.284 Y139.932
G1 X3.417 Y139.799
G1 X8.583 Y134.633 E.22446
G1 X8.716 Y134.5
G1 X8.716 Y133.966
G1 X8.583 Y134.1
G1 X3.417 Y139.265 E.22445
G1 X3.284 Y139.399
G1 X3.284 Y138.866
G1 X3.417 Y138.732
G1 X8.583 Y133.567 E.22445
G1 X8.716 Y133.433
G1 X8.716 Y132.9
G1 X8.583 Y133.034
G1 X3.417 Y138.199 E.22446
G1 X3.284 Y138.332
G1 X3.284 Y137.799
G1 X3.417 Y137.666
G1 X8.583 Y132.5 E.22446
G1 X8.716 Y132.367
G1 X8.716 Y131.833
G1 X8.583 Y131.967
G1 X3.417 Y137.132 E.22445
G1 X3.284 Y137.266
G1 X3.284 Y136.733
G1 X3.417 Y136.599
G1 X8.583 Y131.434 E.22445
G1 X8.716 Y131.3
G1 X8.716 Y130.767
G1 X8.583 Y130.901
G1 X3.417 Y136.066 E.22446
G1 X3.284 Y136.199
G1 X3.284 Y135.666
G1 X3.417 Y135.533
G1 X8.583 Y130.367 E.22446
G1 X8.716 Y130.234
G1 X8.716 Y129.7
G1 X8.583 Y129.834
G1 X3.417 Y134.999 E.22445
G1 X3.284 Y135.133
G1 X3.284 Y134.6
G1 X3.417 Y134.466
G1 X8.583 Y129.301 E.22445
G1 X8.716 Y129.167
G1 X8.716 Y128.634
G1 X8.583 Y128.767
G1 X3.417 Y133.933 E.22446
G1 X3.284 Y134.066
G1 X3.284 Y133.533
G1 X3.417 Y133.399
G1 X8.583 Y128.234 E.22446
G1 X8.716 Y128.101
G1 X8.716 Y127.567
G1 X8.583 Y127.701
G1 X3.417 Y132.866 E.22445
G1 X3.284 Y133
G1 X3.284 Y132.467
G1 X3.417 Y132.333
G1 X8.583 Y127.168 E.22445
G1 X8.716 Y127.034
G1 X8.716 Y126.501
G1 X8.583 Y126.634
G1 X3.417 Y131.8 E.22446
G1 X3.284 Y131.933
G1 X3.284 Y131.4
G1 X3.417 Y131.266
G1 X8.583 Y126.101 E.22446
G1 X8.716 Y125.968
G1 X8.716 Y125.434
G1 X8.583 Y125.568
G1 X3.417 Y130.733 E.22445
G1 X3.284 Y130.867
G1 X3.284 Y130.334
G1 X3.417 Y130.2
G1 X8.583 Y125.035 E.22445
G1 X8.716 Y124.901
G1 X8.716 Y124.368
G1 X8.583 Y124.501
G1 X3.417 Y129.667 E.22446
G1 X3.284 Y129.8
G1 X3.284 Y129.267
G1 X3.417 Y129.133
G1 X8.583 Y123.968 E.22446
G1 X8.716 Y123.835
G1 X8.716 Y123.301
G1 X8.583 Y123.435
G1 X3.417 Y128.6 E.22445
G1 X3.284 Y128.734
G1 X3.284 Y128.201
G1 X3.417 Y128.067
G1 X8.583 Y122.902 E.22445
G1 X8.716 Y122.768
G1 X8.716 Y122.235
G1 X8.583 Y122.368
G1 X3.417 Y127.534 E.22446
G1 X3.284 Y127.667
G1 X3.284 Y127.134
G1 X3.417 Y127
G1 X8.583 Y121.835 E.22446
G1 X8.716 Y121.702
G1 X8.716 Y121.168
G1 X8.583 Y121.302
G1 X3.417 Y126.467 E.22446
G1 X3.284 Y126.601
G1 X3.284 Y126.068
G1 X3.417 Y125.934
G1 X8.583 Y120.769 E.22446
G1 X8.716 Y120.635
G1 X8.716 Y120.102
G1 X8.583 Y120.235
G1 X3.417 Y125.401 E.22446
G1 X3.284 Y125.534
G1 X3.284 Y125.001
G1 X3.417 Y124.867
G1 X8.583 Y119.702 E.22446
G1 X8.716 Y119.568
G1 X8.716 Y119.035
G1 X8.583 Y119.169
G1 X3.417 Y124.334 E.22446
G1 X3.284 Y124.468
G1 X3.284 Y123.934
G1 X3.417 Y123.801
G1 X8.583 Y118.636 E.22446
G1 X8.716 Y118.502
G1 X8.716 Y117.969
G1 X8.583 Y118.102
G1 X3.417 Y123.268 E.22446
G1 X3.284 Y123.401
G1 X3.284 Y122.868
G1 X3.417 Y122.734
G1 X8.583 Y117.569 E.22446
G1 X8.716 Y117.435
G1 X8.716 Y116.902
G1 X8.583 Y117.036
G1 X3.417 Y122.201 E.22446
G1 X3.284 Y122.335
G1 X3.284 Y121.801
G1 X3.417 Y121.668
G1 X8.583 Y116.503 E.22446
G1 X8.716 Y116.369
G1 X8.716 Y115.836
G1 X8.583 Y115.969
G1 X3.417 Y121.135 E.22446
G1 X3.284 Y121.268
G1 X3.284 Y120.735
G1 X3.417 Y120.601
G1 X8.583 Y115.436 E.22446
G1 X8.716 Y115.302
G1 X8.716 Y114.769
G1 X8.583 Y114.903
G1 X3.417 Y120.068 E.22446
G1 X3.284 Y120.202
G1 X3.284 Y119.668
G1 X3.417 Y119.535
G1 X8.583 Y114.37 E.22446
G1 X8.716 Y114.236
G1 X8.716 Y113.703
G1 X8.583 Y113.836
G1 X3.417 Y119.002 E.22446
G1 X3.284 Y119.135
G1 X3.284 Y118.602
G1 X3.417 Y118.468
G1 X8.583 Y113.303 E.22446
G1 X8.716 Y113.169
G1 X8.716 Y112.636
G1 X8.583 Y112.77
G1 X3.417 Y117.935 E.22446
G1 X3.284 Y118.069
G1 X3.284 Y117.535
G1 X3.417 Y117.402
G1 X8.583 Y112.237 E.22445
G1 X8.716 Y112.103
G1 X8.716 Y111.57
G1 X8.583 Y111.703
G1 X3.417 Y116.869 E.22445
G1 X3.284 Y117.002
G1 X3.284 Y116.469
G1 X3.417 Y116.335
G1 X8.583 Y111.17 E.22445
G1 X8.716 Y111.036
G1 X8.716 Y110.503
G1 X8.583 Y110.637
G1 X3.417 Y115.802 E.22445
G1 X3.284 Y115.936
G1 X3.284 Y115.402
G1 X3.417 Y115.269
G1 X8.583 Y110.103 E.22445
G1 X8.716 Y109.97
G1 X8.716 Y109.437
G1 X8.583 Y109.57
G1 X3.417 Y114.735 E.22445
G1 X3.284 Y114.869
G1 X3.284 Y114.336
G1 X3.417 Y114.202
G1 X8.583 Y109.037 E.22445
G1 X8.716 Y108.903
G1 X8.716 Y108.37
G1 X8.583 Y108.504
G1 X3.417 Y113.669 E.22446
G1 X3.284 Y113.803
G1 X3.284 Y113.269
G1 X3.417 Y113.136
G1 X8.583 Y107.97 E.22445
G1 X8.716 Y107.837
G1 X8.716 Y107.304
G1 X8.583 Y107.437
G1 X3.417 Y112.602 E.22445
G1 X3.284 Y112.736
G1 X3.284 Y112.203
G1 X3.417 Y112.069
G1 X8.583 Y106.904 E.22446
G1 X8.716 Y106.77
G1 X8.716 Y106.237
G1 X8.583 Y106.371
G1 X3.417 Y111.536 E.22446
G1 X3.284 Y111.67
G1 X3.284 Y111.136
G1 X3.417 Y111.003
G1 X8.583 Y105.837 E.22445
G1 X8.716 Y105.704
G1 X8.716 Y105.171
G1 X8.583 Y105.304
G1 X3.417 Y110.469 E.22445
G1 X3.284 Y110.603
G1 X3.284 Y110.07
G1 X3.417 Y109.936
G1 X8.583 Y104.771 E.22446
G1 X8.716 Y104.637
G1 X8.716 Y104.104
G1 X8.583 Y104.238
G1 X3.417 Y109.403 E.22446
G1 X3.284 Y109.537
G1 X3.284 Y109.003
G1 X3.417 Y108.87
G1 X8.583 Y103.704 E.22445
G1 X8.716 Y103.571
G1 X8.716 Y103.038
G1 X8.583 Y103.171
G1 X3.417 Y108.336 E.22445
G1 X3.284 Y108.47
G1 X3.284 Y107.937
G1 X3.417 Y107.803
G1 X8.583 Y102.638 E.22446
G1 X8.716 Y102.504
G1 X8.716 Y101.971
G1 X8.583 Y102.105
G1 X3.417 Y107.27 E.22446
G1 X3.284 Y107.404
G1 X3.284 Y106.87
G1 X3.417 Y106.737
G1 X8.583 Y101.571 E.22445
G1 X8.716 Y101.438
G1 X8.716 Y100.904
G1 X8.583 Y101.038
G1 X3.417 Y106.203 E.22445
G1 X3.284 Y106.337
G1 X3.284 Y105.804
G1 X3.417 Y105.67
G1 X8.583 Y100.505 E.22446
G1 X8.716 Y100.371
G1 X8.716 Y99.838
G1 X8.583 Y99.972
G1 X3.417 Y105.137 E.22446
G1 X3.284 Y105.27
G1 X3.284 Y104.737
G1 X3.417 Y104.604
G1 X8.583 Y99.438 E.22445
G1 X8.716 Y99.305
G1 X8.716 Y98.771
G1 X8.583 Y98.905
G1 X3.417 Y104.07 E.22445
G1 X3.284 Y104.204
G1 X3.284 Y103.671
G1 X3.417 Y103.537
G1 X8.583 Y98.372 E.22446
G1 X8.716 Y98.238
G1 X8.716 Y97.705
G1 X8.583 Y97.839
G1 X3.417 Y103.004 E.22446
G1 X3.284 Y103.137
G1 X3.284 Y102.604
G1 X3.417 Y102.471
G1 X8.583 Y97.305 E.22445
G1 X8.716 Y97.172
G1 X8.716 Y96.638
G1 X8.583 Y96.772
G1 X3.417 Y101.937 E.22445
G1 X3.284 Y102.071
G1 X3.284 Y101.538
G1 X3.417 Y101.404
G1 X8.583 Y96.239 E.22446
G1 X8.716 Y96.105
G1 X8.716 Y95.572
G1 X8.583 Y95.706
G1 X3.417 Y100.871 E.22446
G1 X3.284 Y101.004
G1 X3.284 Y100.471
G1 X3.417 Y100.338
G1 X8.583 Y95.172 E.22445
G1 X8.716 Y95.039
G1 X8.716 Y94.505
G1 X8.583 Y94.639
G1 X3.417 Y99.804 E.22445
G1 X3.284 Y99.938
G1 X3.284 Y99.405
G1 X3.417 Y99.271
G1 X8.583 Y94.106 E.22446
G1 X8.716 Y93.972
G1 X8.716 Y93.439
G1 X8.583 Y93.573
G1 X3.417 Y98.738 E.22446
G1 X3.284 Y98.871
G1 X3.284 Y98.338
G1 X3.417 Y98.204
G1 X8.583 Y93.039 E.22445
G1 X8.716 Y92.906
G1 X8.716 Y92.372
G1 X8.583 Y92.506
G1 X3.417 Y97.671 E.22445
G1 X3.284 Y97.805
G1 X3.284 Y97.272
G1 X3.417 Y97.138
G1 X8.583 Y91.973 E.22446
G1 X8.716 Y91.839
G1 X8.716 Y91.306
G1 X8.583 Y91.439
G1 X3.417 Y96.605 E.22446
G1 X3.284 Y96.738
G1 X3.284 Y96.205
G1 X3.417 Y96.071
G1 X8.583 Y90.906 E.22445
G1 X8.716 Y90.773
G1 X8.716 Y90.239
G1 X8.583 Y90.373
G1 X3.417 Y95.538 E.22445
G1 X3.284 Y95.672
G1 X3.284 Y95.139
G1 X3.417 Y95.005
G1 X8.583 Y89.84 E.22446
G1 X8.716 Y89.706
G1 X8.716 Y89.173
G1 X8.583 Y89.306
G1 X3.417 Y94.472 E.22446
G1 X3.284 Y94.605
G1 X3.284 Y94.072
G1 X3.417 Y93.938
G1 X8.583 Y88.773 E.22445
G1 X8.716 Y88.64
G1 X8.716 Y88.106
G1 X8.583 Y88.24
G1 X3.417 Y93.405 E.22445
G1 X3.284 Y93.539
G1 X3.284 Y93.006
G1 X3.417 Y92.872
G1 X8.583 Y87.707 E.22446
G1 X8.716 Y87.573
G1 X8.716 Y87.04
G1 X8.583 Y87.173
G1 X3.417 Y92.339 E.22446
G1 X3.284 Y92.472
G1 X3.284 Y91.939
G1 X3.417 Y91.805
G1 X8.583 Y86.64 E.22445
G1 X8.716 Y86.507
G1 X8.716 Y85.973
G1 X8.583 Y86.107
G1 X3.417 Y91.272 E.22445
G1 X3.284 Y91.406
G1 X3.284 Y90.873
G1 X3.417 Y90.739
G1 X8.583 Y85.574 E.22446
G1 X8.716 Y85.44
G1 X8.716 Y84.907
G1 X8.583 Y85.04
G1 X3.417 Y90.206 E.22446
G1 X3.284 Y90.339
G1 X3.284 Y89.806
G1 X3.417 Y89.672
G1 X8.583 Y84.507 E.22445
G1 X8.716 Y84.373
G1 X8.716 Y83.84
G1 X8.583 Y83.974
G1 X3.417 Y89.139 E.22445
G1 X3.284 Y89.273
G1 X3.284 Y88.74
G1 X3.417 Y88.606
G1 X8.583 Y83.441 E.22446
G1 X8.716 Y83.307
G1 X8.716 Y82.774
G1 X8.583 Y82.907
M73 P98 R0
G1 X3.417 Y88.073 E.22446
G1 X3.284 Y88.206
G1 X3.284 Y87.673
G1 X3.417 Y87.539
G1 X8.583 Y82.374 E.22446
G1 X8.716 Y82.24
G1 X8.716 Y81.707
G1 X8.583 Y81.841
G1 X3.417 Y87.006 E.22446
G1 X3.284 Y87.14
G1 X3.284 Y86.606
G1 X3.417 Y86.473
G1 X8.583 Y81.308 E.22446
G1 X8.716 Y81.174
G1 X8.716 Y80.641
G1 X8.583 Y80.774
G1 X3.417 Y85.94 E.22445
G1 X3.284 Y86.073
G1 X3.284 Y85.54
G1 X3.417 Y85.406
G1 X8.583 Y80.241 E.22445
G1 X8.716 Y80.107
G1 X8.716 Y79.574
G1 X8.583 Y79.708
G1 X3.417 Y84.873 E.22445
G1 X3.284 Y85.007
G1 X3.284 Y84.473
G1 X3.417 Y84.34
G1 X8.583 Y79.175 E.22445
G1 X8.716 Y79.041
G1 X8.716 Y78.508
G1 X8.583 Y78.641
G1 X3.417 Y83.807 E.22445
G1 X3.284 Y83.94
G1 X3.284 Y83.407
G1 X3.417 Y83.273
G1 X8.583 Y78.108 E.22445
G1 X8.716 Y77.974
G1 X8.716 Y77.441
G1 X8.583 Y77.575
G1 X3.417 Y82.74 E.22445
G1 X3.284 Y82.874
G1 X3.284 Y82.34
G1 X3.417 Y82.207
G1 X8.583 Y77.042 E.22445
G1 X8.716 Y76.908
G1 X8.716 Y76.375
G1 X8.583 Y76.508
G1 X3.417 Y81.674 E.22445
G1 X3.284 Y81.807
G1 X3.284 Y81.274
G1 X3.417 Y81.14
G1 X8.583 Y75.975 E.22445
G1 X8.716 Y75.841
G1 X8.716 Y75.308
G1 X8.583 Y75.442
G1 X3.417 Y80.607 E.22445
G1 X3.284 Y80.741
G1 X3.284 Y80.207
G1 X3.417 Y80.074
G1 X8.583 Y74.909 E.22445
G1 X8.716 Y74.775
G1 X8.716 Y74.242
G1 X8.583 Y74.375
G1 X3.417 Y79.54 E.22445
G1 X3.284 Y79.674
G1 X3.284 Y79.141
G1 X3.417 Y79.007
G1 X8.583 Y73.842 E.22445
G1 X8.716 Y73.708
G1 X8.716 Y73.175
G1 X8.583 Y73.309
G1 X3.417 Y78.474 E.22445
G1 X3.284 Y78.608
G1 X3.284 Y78.074
G1 X3.417 Y77.941
G1 X8.583 Y72.775 E.22445
G1 X8.716 Y72.642
G1 X8.716 Y72.109
G1 X8.583 Y72.242
G1 X3.417 Y77.407 E.22445
G1 X3.284 Y77.541
G1 X3.284 Y77.008
G1 X3.417 Y76.874
G1 X8.583 Y71.709 E.22445
G1 X8.716 Y71.575
G1 X8.716 Y71.042
G1 X8.583 Y71.176
G1 X3.417 Y76.341 E.22445
G1 X3.284 Y76.475
G1 X3.284 Y75.941
G1 X3.417 Y75.808
G1 X8.583 Y70.642 E.22445
G1 X8.716 Y70.509
G1 X8.716 Y69.976
G1 X8.583 Y70.109
G1 X3.417 Y75.274 E.22445
G1 X3.284 Y75.408
G1 X3.284 Y74.875
G1 X3.417 Y74.741
G1 X8.583 Y69.576 E.22445
G1 X8.716 Y69.442
G1 X8.716 Y68.909
G1 X8.583 Y69.043
G1 X3.417 Y74.208 E.22445
G1 X3.284 Y74.342
G1 X3.284 Y73.808
G1 X3.417 Y73.675
G1 X8.583 Y68.509 E.22445
G1 X8.716 Y68.376
G1 X8.716 Y67.843
G1 X8.583 Y67.976
G1 X3.417 Y73.141 E.22445
G1 X3.284 Y73.275
G1 X3.284 Y72.742
G1 X3.417 Y72.608
G1 X8.583 Y67.443 E.22445
G1 X8.716 Y67.309
G1 X8.716 Y66.776
G1 X8.583 Y66.91
G1 X3.417 Y72.075 E.22445
G1 X3.284 Y72.209
G1 X3.284 Y71.675
G1 X3.417 Y71.542
G1 X8.583 Y66.376 E.22445
G1 X8.716 Y66.243
G1 X8.716 Y65.709
G1 X8.583 Y65.843
G1 X3.417 Y71.008 E.22445
G1 X3.284 Y71.142
G1 X3.284 Y70.609
G1 X3.417 Y70.475
G1 X8.583 Y65.31 E.22446
G1 X8.716 Y65.176
G1 X8.716 Y64.643
G1 X8.583 Y64.777
G1 X3.417 Y69.942 E.22445
G1 X3.284 Y70.075
G1 X3.284 Y69.542
G1 X3.417 Y69.409
G1 X8.583 Y64.243 E.22445
G1 X8.716 Y64.11
G1 X8.716 Y63.576
G1 X8.583 Y63.71
G1 X3.417 Y68.875 E.22445
G1 X3.284 Y69.009
G1 X3.284 Y68.476
G1 X3.417 Y68.342
G1 X8.583 Y63.177 E.22446
G1 X8.716 Y63.043
G1 X8.716 Y62.51
G1 X8.583 Y62.644
G1 X3.417 Y67.809 E.22446
G1 X3.284 Y67.942
G1 X3.284 Y67.409
G1 X3.417 Y67.276
G1 X8.583 Y62.11 E.22445
G1 X8.716 Y61.977
G1 X8.716 Y61.443
G1 X8.583 Y61.577
G1 X3.417 Y66.742 E.22445
G1 X3.284 Y66.876
G1 X3.284 Y66.343
G1 X3.417 Y66.209
G1 X8.583 Y61.044 E.22446
G1 X8.716 Y60.91
G1 X8.716 Y60.377
G1 X8.583 Y60.511
G1 X3.417 Y65.676 E.22446
G1 X3.284 Y65.809
G1 X3.284 Y65.276
G1 X3.417 Y65.143
G1 X8.583 Y59.977 E.22445
G1 X8.716 Y59.844
G1 X8.716 Y59.31
G1 X8.583 Y59.444
G1 X3.417 Y64.609 E.22445
G1 X3.284 Y64.743
G1 X3.284 Y64.21
G1 X3.417 Y64.076
G1 X8.583 Y58.911 E.22446
G1 X8.716 Y58.777
G1 X8.716 Y58.244
G1 X8.583 Y58.378
G1 X3.417 Y63.543 E.22446
G1 X3.284 Y63.676
G1 X3.284 Y63.143
G1 X3.417 Y63.01
G1 X8.583 Y57.844 E.22445
G1 X8.716 Y57.711
G1 X8.716 Y57.177
G1 X8.583 Y57.311
G1 X3.417 Y62.476 E.22445
G1 X3.284 Y62.61
G1 X3.284 Y62.077
G1 X3.417 Y61.943
G1 X8.583 Y56.778 E.22446
G1 X8.716 Y56.644
G1 X8.716 Y56.111
G1 X8.583 Y56.244
G1 X3.417 Y61.41 E.22446
G1 X3.284 Y61.543
G1 X3.284 Y61.01
G1 X3.417 Y60.876
G1 X8.583 Y55.711 E.22445
G1 X8.716 Y55.578
G1 X8.716 Y55.044
G1 X8.583 Y55.178
G1 X3.417 Y60.343 E.22445
G1 X3.284 Y60.477
G1 X3.284 Y59.944
G1 X3.417 Y59.81
G1 X8.583 Y54.645 E.22446
G1 X8.716 Y54.511
G1 X8.716 Y53.978
G1 X8.583 Y54.111
G1 X3.417 Y59.277 E.22446
G1 X3.284 Y59.41
G1 X3.284 Y58.877
G1 X3.417 Y58.743
G1 X8.583 Y53.578 E.22445
G1 X8.716 Y53.445
G1 X8.716 Y52.911
G1 X8.583 Y53.045
G1 X3.417 Y58.21 E.22445
G1 X3.284 Y58.344
G1 X3.284 Y57.811
G1 X3.417 Y57.677
G1 X8.583 Y52.512 E.22446
G1 X8.716 Y52.378
G1 X8.716 Y51.845
G1 X8.583 Y51.978
G1 X3.417 Y57.144 E.22446
G1 X3.284 Y57.277
G1 X3.284 Y56.744
G1 X3.417 Y56.61
G1 X8.583 Y51.445 E.22445
G1 X8.716 Y51.312
G1 X8.716 Y50.778
G1 X8.583 Y50.912
G1 X3.417 Y56.077 E.22445
G1 X3.284 Y56.211
G1 X3.284 Y55.678
G1 X3.417 Y55.544
G1 X8.583 Y50.379 E.22446
G1 X8.716 Y50.245
G1 X8.716 Y49.712
G1 X8.583 Y49.845
G1 X3.417 Y55.011 E.22446
G1 X3.284 Y55.144
G1 X3.284 Y54.611
G1 X3.417 Y54.477
G1 X8.583 Y49.312 E.22445
G1 X8.716 Y49.179
G1 X8.716 Y48.645
G1 X8.583 Y48.779
G1 X3.417 Y53.944 E.22445
G1 X3.284 Y54.078
G1 X3.284 Y53.545
G1 X3.417 Y53.411
G1 X8.583 Y48.246 E.22445
G1 X8.716 Y48.112
G1 X8.716 Y47.579
G1 X8.583 Y47.712
G1 X3.417 Y52.878 E.22445
G1 X3.284 Y53.011
G1 X3.284 Y52.478
G1 X3.417 Y52.344
G1 X8.583 Y47.179 E.22445
G1 X8.716 Y47.045
G1 X8.716 Y46.512
G1 X8.583 Y46.646
G1 X3.417 Y51.811 E.22445
G1 X3.284 Y51.945
G1 X3.284 Y51.411
G1 X3.417 Y51.278
G1 X8.583 Y46.113 E.22445
G1 X8.716 Y45.979
M73 P99 R0
G1 X8.716 Y45.446
G1 X8.583 Y45.579
G1 X3.417 Y50.745 E.22445
G1 X3.284 Y50.878
G1 X3.284 Y50.345
G1 X3.417 Y50.211
G1 X8.583 Y45.046 E.22445
G1 X8.716 Y44.912
G1 X8.716 Y44.379
G1 X8.583 Y44.513
G1 X3.417 Y49.678 E.22445
G1 X3.284 Y49.812
G1 X3.284 Y49.278
G1 X3.417 Y49.145
G1 X8.583 Y43.98 E.22445
G1 X8.716 Y43.846
G1 X8.716 Y43.313
G1 X8.583 Y43.446
G1 X3.417 Y48.612 E.22445
G1 X3.284 Y48.745
G1 X3.284 Y48.212
G1 X3.417 Y48.078
G1 X8.583 Y42.913 E.22445
G1 X8.716 Y42.779
G1 X8.716 Y42.246
G1 X8.583 Y42.38
G1 X3.417 Y47.545 E.22445
G1 X3.284 Y47.679
G1 X3.284 Y47.145
G1 X3.417 Y47.012
G1 X8.583 Y41.847 E.22445
G1 X8.716 Y41.713
G1 X8.716 Y41.18
G1 X8.583 Y41.313
G1 X3.417 Y46.479 E.22445
G1 X3.284 Y46.612
G1 X3.284 Y46.079
G1 X3.417 Y45.945
G1 X8.583 Y40.78 E.22445
G1 X8.716 Y40.646
G1 X8.716 Y40.113
G1 X8.583 Y40.247
G1 X3.417 Y45.412 E.22445
G1 X3.284 Y45.546
G1 X3.284 Y45.012
G1 X3.417 Y44.879
G1 X8.583 Y39.714 E.22445
G1 X8.716 Y39.58
G1 X8.716 Y39.047
G1 X8.583 Y39.18
G1 X3.417 Y44.346 E.22445
G1 X3.284 Y44.479
G1 X3.284 Y43.946
G1 X3.417 Y43.812
G1 X8.583 Y38.647 E.22445
G1 X8.716 Y38.513
G1 X8.716 Y37.98
G1 X8.583 Y38.114
G1 X3.417 Y43.279 E.22445
G1 X3.284 Y43.413
G1 X3.284 Y42.879
G1 X3.417 Y42.746
G1 X8.583 Y37.58 E.22445
G1 X8.716 Y37.447
G1 X8.716 Y36.914
G1 X8.583 Y37.047
G1 X3.417 Y42.212 E.22445
G1 X3.284 Y42.346
G1 X3.284 Y41.813
G1 X3.417 Y41.679
G1 X8.583 Y36.514 E.22445
G1 X8.716 Y36.38
G1 X8.716 Y35.847
G1 X8.583 Y35.981
G1 X3.417 Y41.146 E.22445
G1 X3.284 Y41.28
G1 X3.284 Y40.746
G1 X3.417 Y40.613
G1 X8.583 Y35.447 E.22445
G1 X8.716 Y35.314
G1 X8.716 Y34.781
G1 X8.583 Y34.914
G1 X3.417 Y40.079 E.22445
G1 X3.284 Y40.213
G1 X3.284 Y39.68
G1 X3.417 Y39.546
G1 X8.583 Y34.381 E.22445
G1 X8.716 Y34.247
G1 X8.716 Y33.714
G1 X8.583 Y33.848
G1 X3.417 Y39.013 E.22445
G1 X3.284 Y39.147
G1 X3.284 Y38.613
G1 X3.417 Y38.48
G1 X13.48 Y28.417 E.43726
G1 X13.613 Y28.284
G1 X13.08 Y28.284
G1 X12.946 Y28.417
G1 X3.417 Y37.946 E.41408
G1 X3.284 Y38.08
G1 X3.284 Y37.547
G1 X3.417 Y37.413
G1 X12.413 Y28.417 E.39091
G1 X12.547 Y28.284
G1 X12.014 Y28.284
G1 X11.88 Y28.417
G1 X3.417 Y36.88 E.36774
G1 X3.284 Y37.014
G1 X3.284 Y36.48
G1 X3.417 Y36.347
G1 X11.347 Y28.417 E.34456
G1 X11.48 Y28.284
G1 X10.947 Y28.284
G1 X10.813 Y28.417
G1 X3.417 Y35.813 E.32139
G1 X3.284 Y35.947
G1 X3.284 Y35.414
G1 X3.417 Y35.28
G1 X10.28 Y28.417 E.29822
G1 X10.414 Y28.284
G1 X9.88 Y28.284
G1 X9.747 Y28.417
G1 X3.417 Y34.747 E.27505
G1 X3.284 Y34.881
G1 X3.284 Y34.347
G1 X3.417 Y34.214
G1 X9.214 Y28.417 E.25187
G1 X9.347 Y28.284
G1 X8.814 Y28.284
G1 X8.68 Y28.417
G1 X3.417 Y33.68 E.2287
G1 X3.284 Y33.814
G1 X3.284 Y33.281
G1 X3.417 Y33.147
G1 X8.147 Y28.417 E.20553
G1 X8.281 Y28.284
G1 X7.747 Y28.284
G1 X7.614 Y28.417
G1 X3.417 Y32.614 E.18236
G1 X3.284 Y32.747
G1 X3.284 Y32.214
G1 X3.417 Y32.081
G1 X7.081 Y28.417 E.15918
G1 X7.214 Y28.284
G1 X6.681 Y28.284
G1 X6.547 Y28.417
G1 X3.417 Y31.547 E.13601
G1 X3.284 Y31.681
G1 X3.284 Y31.148
G1 X3.417 Y31.014
G1 X6.014 Y28.417 E.11284
G1 X6.148 Y28.284
G1 X5.614 Y28.284
G1 X5.481 Y28.417
G1 X3.417 Y30.481 E.08967
G1 X3.284 Y30.614
G1 X3.284 Y30.081
G1 X3.417 Y29.948
G1 X4.948 Y28.417 E.06649
G1 X5.081 Y28.284
G1 X4.548 Y28.284
G1 X4.414 Y28.417
G1 X3.417 Y29.414 E.04332
G1 X3.284 Y29.548
G1 X3.284 Y29.015
G1 X3.417 Y28.881
G1 X3.881 Y28.417 E.02015
; close powerlost recovery
M1003 S0
; WIPE_START
G1 F11933.819
M204 S10000
G1 X3.417 Y28.881 E-.24917
G1 X3.284 Y29.015 E-.07182
G1 X3.284 Y29.548 E-.20264
G1 X3.417 Y29.414 E-.07182
G1 X3.724 Y29.108 E-.16455
; WIPE_END
G1 E-.04 F1800
G17
G3 Z1.6 I1.217 J0 P1  F36000
M106 S0
M106 P2 S0
M981 S0 P20000 ; close spaghetti detector
; FEATURE: Custom
; MACHINE_END_GCODE_START
; filament end gcode 

;======== P2S end gcode ==========
;===== 2026/05/18 =====
M400 ; wait for buffer to clear
G92 E0 ; zero the extruder
M211 Z1

G90
G1 Z1.6 F900 ; lower z a little
M1002 judge_flag timelapse_record_flag
M622 J1
    G150.3
    M400 ; wait all motion done
    M991 S0 P-1 ;end smooth timelapse at safe pos
    M400 S5 ;wait for last picture to be taken
M623  ;end of "timelapse_record_flag

G90
G1 Z11.2 F900 ; lower z a little

M140 S0 ; turn off bed
M106 S0 ; turn off fan
M106 P2 S0 ; turn off remote part cooling fan
M106 P3 S0 ; turn off chamber cooling fan
M106 P10 S0 ; turn off left aux fan

; pull back filament to AMS
M620 S65535
T65535
G150.1 F8000
M621 S65535

G150.3
M104 S0 ; turn off hotend
M400 ; wait all motion done
M17 S
M17 Z0.4 ; lower z motor current to reduce impact if there is something in the bottom

    
        G1 Z80.6 F600
        G1 Z78.6
    

M400 P100
M17 R ; restore z current


M220 S100  ; Reset feedrate magnitude
M201.2 K1.0 ; Reset acc magnitude
M73.2 R1.0 ;Reset left time magnitude
M1002 set_gcode_claim_speed_level : 0

M1015.3 S0 ;disable clog detect
M1015.4 S0 K0 ;disable air printing detect

;=====printer finish air purification=========
M622.1 S0
M1002 judge_flag print_finish_air_filt_flag

M622 J1
M1002 gcode_claim_action : 66
M145 P1
M106 P2 S255
M400 S180
M106 P2 S0
M623

M622 J2
M1002 gcode_claim_action : 66
M145 P0
M106 P3 S255
M400 S180
M106 P3 S0
M623
;=====printer finish air purification=========

;=====printer finish  sound=========
M17
M400 S1
M1006 S1
M1006 A53 B10 L50 C53 D10 M50 E53 F10 N50 
M1006 A57 B10 L50 C57 D10 M50 E57 F10 N50 
M1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 
M1006 A53 B10 L50 C53 D10 M50 E53 F10 N50 
M1006 A57 B10 L50 C57 D10 M50 E57 F10 N50 
M1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 
M1006 A48 B10 L50 C48 D10 M50 E48 F10 N50 
M1006 A0 B15 L0 C0 D15 M0 E0 F15 N0 
M1006 A60 B10 L50 C60 D10 M50 E60 F10 N50 
M1006 W
;=====printer finish  sound=========
M400
M18
M73 P100 R0
; EXECUTABLE_BLOCK_END

