# Ship as a Home Assistant add-on, not a custom integration

Family Assist is delivered as an add-on (app) with its own container and ingress web UI. A custom integration would expose entities, services and automations, but it would run inside the Home Assistant core process, could not bring its own `git` and Python dependencies, and would put model-driven file access next to Home Assistant's secrets. Entity and service access is out of scope for v1, so the isolation of an add-on costs nothing.
