class EditableRoute(models.Model):
    route_type = models.CharField(
        choices=NavigationTask.NAVIGATION_TASK_TYPES, default=NavigationTask.PRECISION, max_length=200
    )
    name = models.CharField(max_length=200, help_text="User-friendly name")
    route = MyPickledObjectField(default=dict)
    thumbnail = models.ImageField(upload_to="route_thumbnails/", blank=True, null=True)

    class Meta:
        ordering = ("name", "pk")

    @classmethod
    def get_for_user(cls, user: MyUser) -> QuerySet:
        return get_objects_for_user(
            user, "display.change_editableroute", klass=EditableRoute, accept_global_perms=False
        )

    def create_thumbnail(self) -> BytesIO:
        """
        Finds the smallest Zoom tile and returns this
        """
        from display.map_plotter import plot_editable_route

        image_stream = plot_editable_route(self)
        return image_stream

    def __str__(self):
        return self.name

    def get_features_type(self, feature_type: str) -> List[Dict]:
        return [item for item in self.route if item["feature_type"] == feature_type]

    def get_feature_type(self, feature_type: str) -> Optional[Dict]:
        try:
            return self.get_features_type(feature_type)[0]
        except IndexError:
            return None

    @staticmethod
    def get_feature_coordinates(feature: Dict, flip: bool = True) -> List[Tuple[float, float]]:
        """
        Switch lon, lat to lat, lon.
        :param feature:
        :return:
        """
        try:
            coordinates = feature["geojson"]["geometry"]["coordinates"]
            if feature["geojson"]["geometry"]["type"] == "Polygon":
                coordinates = coordinates[0]
            if flip:
                return [tuple(reversed(item)) for item in coordinates]
        except KeyError as e:
            raise ValidationError(f"Malformed internal route: {e}")
        return coordinates

    def create_landing_route(self):
        route = Route.objects.create(name="", waypoints=[], use_procedure_turns=False)
        self.amend_route_with_additional_features(route)
        if route.landing_gates is None:
            raise ValidationError("Route must have a landing gate")
        route.waypoints = route.landing_gates
        route.save()
        return route

    def create_precision_route(self, use_procedure_turns: bool) -> Optional[Route]:
        from display.convert_flightcontest_gpx import build_waypoint
        from display.convert_flightcontest_gpx import create_precision_route_from_waypoint_list

        track = self.get_feature_type("track")
        waypoint_list = []
        if track is None:
            return None
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(
                    item["name"],
                    latitude,
                    longitude,
                    item["gateType"],
                    item["gateWidth"],
                    item["timeCheck"],
                    item["timeCheck"],  # We do not include gate check in GUI
                )
            )
        route = create_precision_route_from_waypoint_list(track["name"], waypoint_list, use_procedure_turns)
        self.amend_route_with_additional_features(route)
        return route

    def create_anr_route(self, rounded_corners: bool, corridor_width: float, scorecard: Scorecard) -> Route:
        from display.convert_flightcontest_gpx import build_waypoint
        from display.convert_flightcontest_gpx import create_anr_corridor_route_from_waypoint_list

        track = self.get_feature_type("track")
        waypoint_list = []
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(item["name"], latitude, longitude, "secret", item["gateWidth"], False, False)
            )
        waypoint_list[0].type = STARTINGPOINT
        waypoint_list[0].gate_check = True
        waypoint_list[0].time_check = True
        waypoint_list[0].width = scorecard.get_extended_gate_width_for_gate_type(STARTINGPOINT)

        waypoint_list[-1].type = FINISHPOINT
        waypoint_list[-1].gate_check = True
        waypoint_list[-1].time_check = True
        waypoint_list[-1].width = scorecard.get_extended_gate_width_for_gate_type(FINISHPOINT)

        logger.debug(f"Created waypoints {waypoint_list}")
        route = create_anr_corridor_route_from_waypoint_list(
            track["name"], waypoint_list, rounded_corners, corridor_width=corridor_width
        )
        self.amend_route_with_additional_features(route)
        return route

    def create_airsports_route(self, rounded_corners: bool) -> Route:
        from display.convert_flightcontest_gpx import build_waypoint
        from display.convert_flightcontest_gpx import create_anr_corridor_route_from_waypoint_list

        track = self.get_feature_type("track")
        waypoint_list = []
        coordinates = self.get_feature_coordinates(track)
        track_points = track["track_points"]
        for index, (latitude, longitude) in enumerate(coordinates):
            item = track_points[index]
            waypoint_list.append(
                build_waypoint(
                    item["name"],
                    latitude,
                    longitude,
                    item["gateType"],
                    item["gateWidth"],
                    item["timeCheck"],
                    item["timeCheck"],
                )
            )
        route = create_anr_corridor_route_from_waypoint_list(track["name"], waypoint_list, rounded_corners)
        self.amend_route_with_additional_features(route)
        return route

    def amend_route_with_additional_features(self, route: Route):
        from display.convert_flightcontest_gpx import create_gate_from_line

        takeoff_gates = self.get_features_type("to")
        for index, takeoff_gate in enumerate(takeoff_gates):
            takeoff_gate_line = self.get_feature_coordinates(takeoff_gate)
            if len(takeoff_gate_line) != 2:
                raise ValidationError("Take-off gate should have exactly 2 points")
            gate = create_gate_from_line(takeoff_gate_line, f"Takeoff {index + 1}", "to")
            gate.gate_line = takeoff_gate_line
            route.takeoff_gates.append(gate)
        landing_gates = self.get_features_type("ldg")
        for index, landing_gate in enumerate(landing_gates):
            landing_gate_line = self.get_feature_coordinates(landing_gate)
            if len(landing_gate_line) != 2:
                raise ValidationError("Landing gate should have exactly 2 points")
            gate = create_gate_from_line(landing_gate_line, f"Landing {index + 1}", "ldg")
            gate.gate_line = landing_gate_line
            route.landing_gates.append(gate)
        route.save()
        # Create prohibited zones
        for zone_type in ("info", "penalty", "prohibited", "gate"):
            for feature in self.get_features_type(zone_type):
                logger.debug(feature)
                Prohibited.objects.create(
                    name=feature["name"],
                    route=route,
                    path=self.get_feature_coordinates(feature, flip=True),
                    type=zone_type,
                    tooltip_position=feature.get("tooltip_position", []),
                )

    @classmethod
    def _create_route_and_thumbnail(cls, name: str, route: list[dict]) -> "EditableRoute":
        editable_route = EditableRoute.objects.create(name=name, route=route)
        try:
            editable_route.thumbnail.save(
                editable_route.name + "_thumbnail.png",
                ContentFile(editable_route.create_thumbnail().getvalue()),
                save=True,
            )
        except:
            logger.exception("Failed creating editable route thumbnail")
        return editable_route

    @classmethod
    def create_from_kml(cls, route_name: str, kml_content: TextIO) -> tuple[Optional["EditableRoute"], list[str]]:
        """Create a route from our own kml format."""
        messages = []
        from display.convert_flightcontest_gpx import load_features_from_kml

        features = load_features_from_kml(kml_content)
        positions = features.get("route", [])
        track = create_track_block([(item[0], item[1]) for item in positions])
        route = [track]
        if take_off_gate_line := features.get("to"):
            if len(take_off_gate_line) == 2:
                route.append(create_takeoff_gate([(item[1], item[0]) for item in take_off_gate_line]))
                messages.append("Found takeoff gate")
        if landing_gate_line := features.get("to"):
            if len(landing_gate_line) == 2:
                route.append(create_landing_gate([(item[1], item[0]) for item in landing_gate_line]))
                messages.append("Found landing gate")
        for name in features.keys():
            logger.debug(f"Found feature {name}")
            try:
                zone_type, zone_name = name.split("_")
                if zone_type == "prohibited":
                    route.append(create_prohibited_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "info":
                    route.append(create_information_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "penalty":
                    route.append(create_penalty_zone([(item[1], item[0]) for item in features[name]], zone_name))
                if zone_type == "gate":
                    route.append(create_gate_polygon([(item[1], item[0]) for item in features[name]], zone_name))
                messages.append(f"Found {zone_type} polygon {zone_name}")
            except ValueError:
                pass
        editable_route = cls._create_route_and_thumbnail(route_name, route)
        logger.debug(messages)
        return editable_route, messages

    @classmethod
    def create_from_csv(cls, name: str, csv_content: list[str]) -> tuple[Optional["EditableRoute"], list[str]]:
        """Create a route from our own CSV format."""
        messages = []
        positions = []
        gate_widths = []
        names = []
        types = []
        try:
            for line in csv_content:
                line = [item.strip() for item in line.split(",")]
                positions.append((float(line[2]), float(line[1])))  # CSV contains longitude, latitude
                names.append(line[0])
                gate_widths.append(float(line[4]))
                types.append(line[3])
            route = [create_track_block(positions, widths=gate_widths, names=names, types=types)]
            editable_route = cls._create_route_and_thumbnail(name, route)
            return editable_route, messages
        except Exception as ex:
            logger.exception("Failure when creating route from csv")
            messages.append(str(ex))
        return None, messages

    @classmethod
    def create_from_gpx(cls, name: str, gpx_content: bytes) -> tuple[Optional["EditableRoute"], list[str]]:
        """
        Create a route from flight contest GPX format. Note that this does not include the waypoint lines that are
        defined in the GPX file, these will be calculated internally.
        """
        gpx = gpxpy.parse(gpx_content)
        waypoint_order = []
        waypoint_definitions = {}
        my_route = []
        messages = []
        logger.debug(f"Routes {gpx.routes}")
        for route in gpx.routes:
            for extension in route.extensions:
                logger.debug(f'Extension {extension.find("route")}')
                if extension.find("route") is not None:
                    route_name = route.name
                    logger.debug("Loading GPX route {}".format(route_name))
                    for point in route.points:
                        waypoint_order.append(point.name)
                gate_extension = extension.find("gate")
                if gate_extension is not None:
                    gate_name = route.name
                    gate_type = gate_extension.attrib["type"].lower()
                    logger.debug(f"Gate {gate_name} is {gate_type}")
                    if gate_type == "to":
                        my_route.append(
                            create_takeoff_gate(
                                (
                                    (route.points[0].longitude, route.points[0].latitude),
                                    (route.points[1].longitude, route.points[1].latitude),
                                )
                            )
                        )
                        messages.append("Found take-off gate")
                    elif gate_type == "ldg":
                        my_route.append(
                            create_landing_gate(
                                (
                                    (route.points[0].longitude, route.points[0].latitude),
                                    (route.points[1].longitude, route.points[1].latitude),
                                )
                            )
                        )
                        messages.append("Found landing gate")
                    else:
                        waypoint_definitions[gate_name] = {
                            "position": (float(gate_extension.attrib["lat"]), float(gate_extension.attrib["lon"])),
                            "width": float(gate_extension.attrib["width"]),
                            "type": gate_type,
                            "time_check": gate_extension.attrib["notimecheck"] == "no"
                        }
        my_route.append(
            create_track_block(
                [waypoint_definitions[name]["position"] for name in waypoint_order],
                names=waypoint_order,
                types=[waypoint_definitions[name]["type"] for name in waypoint_order],
                widths=[waypoint_definitions[name]["width"] for name in waypoint_order],
            )
        )
        logger.debug(f"Found route with {len(waypoint_order)} gates")
        messages.append(f"Found route with {len(waypoint_order)} gates")
        editable_route = cls._create_route_and_thumbnail(name, my_route)
        return editable_route, messages


