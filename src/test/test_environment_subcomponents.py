import numpy as np
import pytest
import io
from matplotlib.testing.decorators import check_figures_equal
from numpy.random import default_rng
from src.models.action_definitions import TurnFunctions, TurnActionEnum
from src.models.fly_spatial_parameters import FlySpatialParameters
from src.models.geometry import standardize_angle, angle_to_unit_vector
from src.models.odor_senses import detect_local_odor_concentration, MAX_HISTORY_LENGTH, OdorHistory
from src.models.odor_plumes import OdorPlumeAllOnes, OdorPlumeAllZeros, PLUME_VIDEO_X_BOUNDS, PLUME_VIDEO_Y_BOUNDS, \
    OdorPlumeRollingRandom
from src.models.render_environment import render_odor_plume_frame_no_fly, gen_arrow_head_marker, FLY_MARKER_SIZE, \
    FLY_MARKER_COLOR, render_oriented_fly
from src.models.wind_directions import WindDirections


def test_fly_should_be_north_of_starting_position_after_walking_north_from_starting_position(fly_spatial_parameters):
    walking_direction = np.array([0, 1])
    fly_spatial_parameters.update_position(walking_direction)
    expected_position = np.array([0, 1])
    assert np.array_equal(fly_spatial_parameters.position, expected_position)


def test_fly_should_be_south_of_starting_position_after_walking_south_from_starting_position(fly_spatial_parameters):
    walking_direction = np.array([0, -1])
    fly_spatial_parameters.update_position(walking_direction)
    expected_position = np.array([0, -1])
    assert np.array_equal(fly_spatial_parameters.position, expected_position)


def test_fly_should_be_east_of_starting_position_after_walking_east_from_starting_position(fly_spatial_parameters):
    walking_direction = np.array([1, 0])
    fly_spatial_parameters.update_position(walking_direction)
    expected_position = np.array([1, 0])
    assert np.array_equal(fly_spatial_parameters.position, expected_position)


def test_fly_should_face_north_after_quarter_turn_ccw(fly_spatial_parameters):
    turn_angle = np.pi / 2
    fly_spatial_parameters.turn(turn_angle)
    expected_angle = np.pi / 2
    assert np.array_equal(fly_spatial_parameters.orientation, expected_angle)


def test_fly_should_face_south_after_quarter_turn_cw(fly_spatial_parameters):
    turn_angle = - np.pi / 2
    fly_spatial_parameters.turn(turn_angle)
    expected_angle = - np.pi / 2
    expected_angle = standardize_angle(expected_angle)
    assert np.array_equal(fly_spatial_parameters.orientation, expected_angle)


def test_fly_should_face_south_after_three_quarters_turn_ccw(fly_spatial_parameters):
    turn_angle = np.pi * 3 / 2
    fly_spatial_parameters.turn(turn_angle)
    expected_angle = - np.pi / 2
    expected_angle = standardize_angle(expected_angle)
    assert np.array_equal(fly_spatial_parameters.orientation, expected_angle)


def test_fly_should_be_north_after_turning_north_and_walking_forward(fly_spatial_parameters):
    turn_angle = np.pi / 2
    fly_spatial_parameters.turn_and_walk(turn_angle)
    expected_position = np.array([0, 1])
    assert np.allclose(fly_spatial_parameters.position, expected_position)


def test_fly_should_be_south_after_turning_south_and_walking_forward(fly_spatial_parameters):
    turn_angle = - np.pi / 2
    fly_spatial_parameters.turn_and_walk(turn_angle)
    expected_position = np.array([0, -1])
    assert np.allclose(fly_spatial_parameters.position, expected_position)


def test_fly_should_face_south_after_upwind_quarter_turn_from_zero_in_southerly_wind(fly_spatial_parameters):
    wind_direction = np.pi / 2
    turn_functions = TurnFunctions(wind_params=WindDirections(wind_angle=wind_direction))
    turn_sign = turn_functions.turn_against_orientation_sign(fly_spatial_parameters.orientation, wind_direction)
    quarter_turn_magnitude = np.pi / 2
    turn_angle = turn_sign * quarter_turn_magnitude
    fly_spatial_parameters.turn(turn_angle)
    expected_angle = 3 * np.pi / 2
    assert np.array_equal(fly_spatial_parameters.orientation, expected_angle)


def test_fly_should_face_north_after_upwind_quarter_turn_from_zero_in_northerly_wind(fly_spatial_parameters):
    wind_direction = 3 * np.pi / 2
    turn_functions = TurnFunctions(wind_params=WindDirections(wind_angle=wind_direction))
    turn_sign = turn_functions.turn_against_orientation_sign(fly_spatial_parameters.orientation, wind_direction)
    quarter_turn_magnitude = np.pi / 2
    fly_spatial_parameters.turn(turn_sign * quarter_turn_magnitude)
    expected_angle = np.pi / 2
    assert np.array_equal(fly_spatial_parameters.orientation, expected_angle)


def test_crosswind_direction_a_should_be_orthogonal_to_wind():
    wind_directions = WindDirections(3 * np.pi / 2)
    wind_direction = angle_to_unit_vector(wind_directions.wind_angle)
    crosswind_direction_a = angle_to_unit_vector(wind_directions.crosswind_a)
    assert np.dot(wind_direction, crosswind_direction_a) == pytest.approx(0)


def test_crosswind_direction_b_should_be_orthogonal_to_wind():
    wind_directions = WindDirections(3 * np.pi / 2)
    wind_direction = angle_to_unit_vector(wind_directions.wind_angle)
    crosswind_direction_b = angle_to_unit_vector(wind_directions.crosswind_b)
    assert np.dot(wind_direction, crosswind_direction_b) == pytest.approx(0)


def test_action_no_turn_should_leave_orientation_alone(fly_spatial_parameters):
    wind_directions = WindDirections(3 * np.pi / 2)
    turn_functions = TurnFunctions(wind_params=wind_directions)
    fly_spatial_parameters.orientation = 0
    fly_spatial_parameters.orientation = \
        turn_functions.turn_functions[TurnActionEnum.NO_TURN](fly_spatial_parameters.orientation)
    assert fly_spatial_parameters.orientation == 0


def test_action_upwind_turn_from_facing_east_in_northerly_wind_should_yield_orientation_at_one_sixth_of_a_full_turn_ccw(
        fly_spatial_parameters):
    wind_directions = WindDirections(3 * np.pi / 2)
    turn_funcs = TurnFunctions(wind_params=wind_directions).turn_functions
    fly_spatial_parameters.orientation = 0
    fly_spatial_parameters.orientation = \
        turn_funcs[TurnActionEnum.UPWIND_TURN](fly_spatial_parameters.orientation)
    expected_angle = np.pi / 6
    assert fly_spatial_parameters.orientation == expected_angle


def test_action_step_upwind_in_westerly_wind_should_yield_walking_angle_easterly(fly_spatial_parameters):
    wind_directions = WindDirections()
    easterly = np.pi
    delta_x = np.cos(wind_directions.upwind)
    delta_y = np.sin(wind_directions.upwind)
    assert np.allclose(easterly, np.angle(delta_x + delta_y * 1j))


def test_consecutive_crosswind_rolling_plume_frames_should_be_displaced_by_1(plume_rolling_random_shift1):
    displacement = 1
    plume_rolling_random_shift1.reset()
    last_frame = plume_rolling_random_shift1.get_previous_frame()
    expected_frame = np.roll(last_frame, shift=displacement)
    consecutive_frame = plume_rolling_random_shift1.frame
    assert np.array_equal(consecutive_frame, expected_frame)


def test_consecutive_crosswind_rolling_plume_frames_should_be_displaced_by_1_after_advancing(
        plume_rolling_random_shift1):
    displacement = 1
    plume_rolling_random_shift1.reset()
    last_frame = plume_rolling_random_shift1.frame
    expected_frame = np.roll(last_frame, shift=displacement)
    plume_rolling_random_shift1.advance()
    consecutive_frame = plume_rolling_random_shift1.frame
    assert np.array_equal(consecutive_frame, expected_frame)


@check_figures_equal(extensions=["png"])
def test_rendering_all_ones_plume_canvas_with_no_fly_creates_1500x900_white_image(fig_test, fig_ref):
    ref_canvas = np.ones([1500, 900])
    ax_ref = fig_ref.subplots()
    ax_ref.imshow(ref_canvas.T, origin='lower', cmap='gray', vmin=0, vmax=1)
    ax_test = fig_test.subplots()
    all_ones_plume = OdorPlumeAllOnes()
    render_odor_plume_frame_no_fly(plume_frame=all_ones_plume.frame, plot_axis=ax_test)


@check_figures_equal(extensions=["png"])
def test_rendering_all_zeros_plume_canvas_with_no_fly_creates_1500x900_black_image(fig_test, fig_ref):
    ref_canvas = np.zeros([1500, 900])
    ax_ref = fig_ref.subplots()
    ax_ref.imshow(ref_canvas.T, origin='lower', cmap='gray', vmin=0, vmax=1)
    ax_test = fig_test.subplots()
    all_zeros_plume = OdorPlumeAllZeros()
    render_odor_plume_frame_no_fly(plume_frame=all_zeros_plume.frame, plot_axis=ax_test)


@check_figures_equal(extensions=["png"])
def test_rendering_all_zeros_plume_canvas_with_fly_at_origin_facing_north_should_add_an_upwards_blue_triangle(fig_test,
                                                                                                              fig_ref):
    ref_canvas = np.zeros([1500, 900])
    ax_ref = fig_ref.subplots()
    ax_ref.imshow(ref_canvas.T, origin='lower', cmap='gray', vmin=0, vmax=1)
    origin = np.array([0, 0])
    north = np.pi / 2
    north_arrow, scale = gen_arrow_head_marker(rot=north)
    ax_ref.scatter(origin[0], origin[1], marker=north_arrow, s=(FLY_MARKER_SIZE * scale) ** 2, c=FLY_MARKER_COLOR)
    ax_test = fig_test.subplots()
    all_zeros_plume = OdorPlumeAllZeros()
    fly = FlySpatialParameters(orientation=north, position=origin)
    ax_test = render_odor_plume_frame_no_fly(plume_frame=all_zeros_plume.frame, plot_axis=ax_test)
    render_oriented_fly(position=fly.position, orientation=fly.orientation, plot_axis=ax_test)


# def test_export_fig_to_rgb_array()

@pytest.fixture
def fly_spatial_parameters():
    return FlySpatialParameters(orientation=0, position=np.array([0, 0]))


@pytest.fixture
def max_history_length():
    return MAX_HISTORY_LENGTH


@pytest.fixture
def odor_history():
    return OdorHistory()


@pytest.fixture
def odor_plume_all_ones():
    return OdorPlumeAllOnes()


@pytest.fixture
def plume_rolling_random_shift1():
    shift_size = 1
    return OdorPlumeRollingRandom(roll_shift_size=shift_size)
