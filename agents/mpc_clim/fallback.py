"""Demand-aware dispatch policy; see docs/GUIDE.md for the agent interface and observation fields."""

import numpy as np


class Agent:
    def __init__(self, config=None):
        static, layout = config["static"], config["layout"]
        edges, lanes = static["edges"], static["lanes"]
        self.edges = edges
        slots = static["action_slots"]
        self.capacity = np.array([edges["u0"][e] for e in slots["edge"]], dtype=float)

        self.demands = [tuple(row) for row in layout["demands"]]
        self.demand_index = {key: i for i, key in enumerate(self.demands)}
        self.stock_index = {tuple(row): i for i, row in enumerate(layout["stock_slots"])}
        self.slot_routes = []
        self.demand_slots = [[] for _ in self.demands]
        chokepoint_index = {node: i for i, node in enumerate(layout["chokepoints"])}
        self.route_chokepoints = []
        for slot, (edge, commodity, lane) in enumerate(zip(slots["edge"], slots["k"], slots["lane"])):
            route = lanes["edges"][lane] if lane is not None else [edge]
            destination = edges["head"][route[-1]]
            demand = self.demand_index.get((destination, commodity))
            self.slot_routes.append((demand, route))
            self.route_chokepoints.append(
                [chokepoint_index[node] for node in lanes["chokepoints"][lane]] if lane is not None else []
            )
            if demand is not None:
                self.demand_slots[demand].append(slot)

        self.pipeline_destinations = {
            (head, commodity): self.demand_index[(head, commodity)]
            for head, commodity in zip(static["sinks"]["node"], static["sinks"]["k"])
            if (head, commodity) in self.demand_index
        }

    def act(self, observation):
        flows = self.capacity * observation["action_mask"]
        week = int(observation["week"][0])
        forecast = observation["demand_forecast.qty"]
        forecast_seen = observation["demand_forecast.qty.observed"]
        stock = observation["stock.qty"]
        stock_seen = observation["stock.qty.observed"]
        backlog = observation["backlog.qty"]
        backlog_seen = observation["backlog.qty.observed"]

        need = np.cumsum(forecast * forecast_seen, axis=1)
        arrivals = np.zeros_like(need)
        pipeline_seen = observation["pipeline.qty.observed"]
        edges = self.edges
        for edge, commodity, arrival_week, quantity, seen in zip(
            observation["pipeline.edge"],
            observation["pipeline.k"],
            observation["pipeline.arrival_week"],
            observation["pipeline.qty"],
            pipeline_seen,
        ):
            if not seen:
                continue
            demand = self.pipeline_destinations.get((edges["head"][edge], commodity))
            offset = int(arrival_week) - week
            if demand is not None and 0 <= offset < need.shape[1]:
                arrivals[demand, offset] += quantity
        arrivals = np.cumsum(arrivals, axis=1)

        current_stock = np.zeros(len(self.demands))
        stock_known = np.ones(len(self.demands), dtype=bool)
        for demand, key in enumerate(self.demands):
            index = self.stock_index.get(key)
            if index is None:
                stock_known[demand] = False
            elif stock_seen[index]:
                current_stock[demand] = stock[index]
            else:
                stock_known[demand] = False

        for demand, slots in enumerate(self.demand_slots):
            if (
                not slots
                or not stock_known[demand]
                or not backlog_seen[demand]
                or not np.all(forecast_seen[demand])
            ):
                continue

            cumulative_need = need[demand] + backlog[demand]
            available = current_stock[demand] + arrivals[demand]
            candidates = []
            for slot in slots:
                _, route = self.slot_routes[slot]
                lead = sum(int(observation["graph_now.tau"][edge]) for edge in route)
                delay = max(lead - 1, 0)
                if delay >= need.shape[1]:
                    continue
                flows[slot] = 0.0
                route_cost = sum(float(observation["graph_now.c"][edge]) for edge in route)
                route_capacity = min(
                    self.capacity[slot] * observation["action_mask"][slot],
                    min(float(observation["graph_now.u"][edge]) for edge in route),
                )
                for chokepoint in self.route_chokepoints[slot]:
                    if observation["graph_now.open.observed"][chokepoint]:
                        route_capacity *= max(float(observation["graph_now.open"][chokepoint]), 0.0)
                if not route_capacity:
                    continue
                candidates.append((route_cost, delay, slot, route_capacity))

            candidates.sort()
            delays = {}
            for slot in slots:
                route = self.slot_routes[slot][1]
                delays[slot] = max(sum(int(observation["graph_now.tau"][edge]) for edge in route) - 1, 0)
            for _, delay, slot, route_capacity in candidates:
                remaining_capacity = route_capacity
                for horizon in range(delay, need.shape[1]):
                    planned = sum(
                        flows[other]
                        for other in slots
                        if delays[other] <= horizon
                    )
                    deficit = cumulative_need[horizon] - available[horizon] - planned
                    if deficit <= 0:
                        continue
                    quantity = min(remaining_capacity, deficit)
                    flows[slot] += quantity
                    remaining_capacity -= quantity
                    if remaining_capacity <= 0:
                        break

        return {"flows": flows}
