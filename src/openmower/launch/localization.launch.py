import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    # Get the launch directory
    package_path = get_package_share_directory('openmower')
    
    
    bringup_path = get_package_share_directory('nav2_bringup')

    namespace = LaunchConfiguration('namespace')
    map_yaml_file = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')
    lifecycle_nodes = ['map_server']

    # Map fully qualified names to relative ones so the node's namespace can be prepended.
    # In case of the transforms (tf), currently, there doesn't seem to be a better alternative
    # https://github.com/ros/geometry2/issues/32
    # https://github.com/ros/robot_state_publisher/pull/30
    # TODO(orduno) Substitute with `PushNodeRemapping`
    #              https://github.com/ros2/launch_ros/issues/56
    remappings = [('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]

    # Create our own temporary YAML files that include substitutions
    param_substitutions = {
        'use_sim_time': use_sim_time,
        'yaml_filename': map_yaml_file,
    }

    configured_params = RewrittenYaml(
        source_file=params_file,
        root_key=namespace,
        param_rewrites=param_substitutions,
        convert_types=True)

    localization_params_path = os.path.join(package_path, 'config', 'robot_localization.yaml')

    return LaunchDescription([
        # Set env var to print messages to stdout immediately
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),

        DeclareLaunchArgument(
            'namespace', default_value='',
            description='Top-level namespace'),

        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(bringup_path, 'maps', 'turtlebot3_world.yaml'),
            description='Full path to map yaml file to load'),

        DeclareLaunchArgument(
            'use_sim_time', default_value='false',
            description='Use simulation (Gazebo) clock if true'),

        DeclareLaunchArgument(
            'autostart', default_value='true',
            description='Automatically startup the nav2 stack'),

        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(package_path, 'config', 'nav2_params.yaml'),
            description='Full path to the ROS2 parameters file to use'),

        TimerAction(period=3.0, actions=[Node(
            package='open_mower_map_server',
            executable='map_server_node',
            name='map_server',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'path': os.getenv('OM_MAP_PATH'),
            }],
            remappings=[
                ('map_grid', 'map'), # occupancy grid topic
                ('map', 'mowing_map'), # map topic
            ],
        )]),

        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_se_odom',
            output='screen',
            parameters=[localization_params_path, {'use_sim_time': use_sim_time}],
            remappings=[
                ('imu/data', 'imu/data_raw'),
            ],
        ),

        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_se_map',
            output='screen',
            parameters=[localization_params_path, {'use_sim_time': use_sim_time}],
            remappings=[
                ('imu/data', 'imu/data_raw'),
                ('odometry/filtered', 'odometry/filtered/map'),
            ],
        ),

        Node(
            package='robot_localization',
            executable='navsat_transform_node',
            name='navsat_transform_node',
            output='screen',
            parameters=[localization_params_path, {
                'use_sim_time': use_sim_time,
                'datum': [float(os.getenv('OM_DATUM_LAT')), float(os.getenv('OM_DATUM_LONG')), 0.0],
            }],
            remappings=[
                ('odometry/filtered', 'odometry/filtered/map'),
                ('imu', 'gps/orientation'),
            ],
        ),
        #tf2_static_tfp
    ])
