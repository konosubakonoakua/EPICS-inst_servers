"""
Classes and objects decribing the movement of items
"""

from math import fabs, tan, radians, sin, cos, sqrt

from ReflectometryServer.geometry import PositionAndAngle, Position

# Tolerance to use when comparing an angle with another angle
ANGULAR_TOLERANCE = 1e-12


class LinearMovementCalc(object):
    """
    A strategy for calculating the interception of the beam with a component that can only move linearly in the Z Y
    plain. E.g. a slit moving vertically to the floor, the position at zero is usually the position of the slit on
    the straight through beam
    """

    def __init__(self, setup):
        """

        Args:
            setup (ReflectometryServer.geometry.PositionAndAngle):
        """
        self._listeners = []
        self._angle = setup.angle
        self._position_at_zero = Position(setup.y, setup.z)
        self._displacement = 0

    def calculate_interception(self, beam):
        """
        Calculate the interception point of the beam and component
        Args:
            beam(PositionAndAngle) : beam to intercept

        Returns: position of the interception

        """
        assert beam is not None
        y_m = self._position_at_zero.y
        z_m = self._position_at_zero.z
        angle_m = self._angle
        y_b = beam.y
        z_b = beam.z
        angle_b = beam.angle

        if fabs(angle_b % 180.0 - angle_m % 180.0) <= ANGULAR_TOLERANCE:
            raise ValueError("No interception between beam and movement")
        elif fabs(angle_b % 180.0) <= ANGULAR_TOLERANCE:
            y, z = self._zero_angle(y_b, self._position_at_zero, self._angle)
        elif fabs(angle_m % 180.0) <= ANGULAR_TOLERANCE:
            y, z = self._zero_angle(y_m, beam, beam.angle)
        elif fabs(angle_m % 180.0 - 90) <= ANGULAR_TOLERANCE or fabs(angle_m % 180.0 + 90) <= ANGULAR_TOLERANCE:
            y, z = self._right_angle(z_m, beam, beam.angle)
        elif fabs(angle_b % 180.0 - 90) <= ANGULAR_TOLERANCE or fabs(angle_b % 180.0 + 90) <= ANGULAR_TOLERANCE:
            y, z = self._right_angle(z_b, self._position_at_zero, self._angle)
        else:
            tan_b = tan(radians(angle_b))
            tan_m = tan(radians(angle_m))
            z = 1/(tan_m - tan_b) * (y_b - y_m + z_m * tan_m - z_b * tan_b)
            y = tan_b * tan_m / (tan_b - tan_m) * (y_m / tan_m - y_b / tan_b + z_b - z_m)

        return Position(y, z)

    def _zero_angle(self, y_zero, position, angle):
        """
        Calculate when one of the angles is zero but not the other
        Args:
            y_zero: the y of the item with zero angle
            position: position of other ray
            angle: angle of other ray

        Returns: y and z of intercept

        """
        y = y_zero
        z = position.z + (y_zero - position.y) / tan(radians(angle))
        return y, z

    def _right_angle(self, z_zero, position, angle):
        """
        Calculate when one of the angles is a right angle but not the other
        Args:
            z_zero: the z of the item with right angle
            position: position of other ray
            angle: angle of other ray

        Returns: y and z of intercept
        """

        y = position.y + (z_zero - position.z) * tan(radians(angle))
        z = z_zero
        return y, z

    def set_distance_relative_to_beam(self, beam, position):
        """
        Set the position of the component relative to the beam for the given value based on its movement strategy.
        For instance this could set the height above the beam for a vertically moving component
        Args:
            beam: the current beam ray to set relative to
            position: the position relative to the beam that the component should be, e.g. height
        """

        self._displacement = position + self._dist_along_axis_from_zero_to_beam_intercept(beam)

    def _dist_along_axis_from_zero_to_beam_intercept(self, beam):
        """
        Distance along the axis of movement from the zero point to where the beam hits that axis.
        Args:
            beam: the beam ray

        Returns: the distance in the positive sense from the zero point to the intercept with the beam

        """
        beam_intercept = self.calculate_interception(beam)
        y_diff = self._position_at_zero.y - beam_intercept.y
        z_diff = self._position_at_zero.z - beam_intercept.z
        dist_to_beam = sqrt(pow(y_diff, 2) + pow(z_diff, 2))
        if y_diff > 0:
            direction = -1.0
        else:
            direction = 1.0
        if (self._angle % 360.0) >= 180.0:
            direction *= -1
        dist_along_axis_from_zero_to_beam_intercept = dist_to_beam * direction
        return dist_along_axis_from_zero_to_beam_intercept

    def sp_position(self):
        """
        Returns (Position): The set point position of this component in mantid coordinates.
        """
        y_value = self._position_at_zero.y + self._displacement * sin(radians(self._angle))
        z_value = self._position_at_zero.z + self._displacement * cos(radians(self._angle))

        return Position(y_value, z_value)

    def set_displacement(self, displacement):
        """
        Set the read back value for the movement. The is the displacement along the axis from the zero point to the
        actual position of the component, in the direction of the axis.
        Args:
            displacement: value along the axis, -ve for before the zero point
        """
        self._displacement = float(displacement)

    def get_distance_relative_to_beam(self, beam):
        """
        Given a beam get the distance of the component along the axis of movement from the intercept of the
        beam with the axis of movement.
        Args:
            beam: beam that the rbv is relative to

        Returns: distance of the component from the beam along the axis of movement

        """
        return self._displacement - self._dist_along_axis_from_zero_to_beam_intercept(beam)

    def get_displacement(self):
        """

        Returns: displacement along a axis from the zero position.

        """
        return self._displacement

# class ArcMovement(PositionAndAngle):
#     """
#     A strategy for calculating the interception of the beam with a component that can only move on a radius
#     """
#
#     def __init__(self, y_center_of_rotation, z_centre_of_rotation):
#         super(ArcMovement, self).__init__(y_center_of_rotation, z_centre_of_rotation, 0)
