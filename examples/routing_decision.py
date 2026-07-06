"""Model routing decision example."""

from kiwi_local_llm_bridge.routing import LLMRouteManager


def build_config() -> dict:
    """Return the smallest config needed for route resolution."""

    return {
        "llm_routing": {
            "enabled": True,
            "allow_client_update": True,
            "default_execution_target": "server_cloud",
            "fallback": {
                "fallback_model_id": "cloud_default",
                "fallback_execution_target": "server_cloud",
            },
        },
        "llm_model_registry": {
            "models": {
                # Cloud models must exist in the registry because the server
                # needs their llm_config_key to call a provider.
                "cloud_default": {
                    "llm_config_key": "CloudProvider",
                    "source": "cloud",
                    "execution_target": "server_cloud",
                    "enabled": True,
                    "visible_to_client": True,
                    "display_name": "Cloud Default",
                },
                # Local models describe what the client can advertise/select.
                "local_demo": {
                    "llm_config_key": "LocalRoute",
                    "source": "local",
                    "execution_target": "client_local",
                    "enabled": True,
                    "visible_to_client": True,
                    "display_name": "Local Demo",
                },
            },
            "defaults": {"global": "cloud_default"},
        },
    }


def main() -> None:
    manager = LLMRouteManager.from_config(build_config())

    # Simulate a client selecting a local model for one session.
    ok, decision, error = manager.update_client_route(
        session_id="session-1",
        keychain_id="device-1",
        llm_model_id="local_demo",
        execution_target="client_local",
    )
    print(f"route_update_ok={ok}")
    print(f"route_update_error={error}")
    print(f"route_update_decision={decision.to_dict() if decision else None}")

    # Later inference requests for the same session reuse that session route.
    resolved = manager.resolve_route(
        session_id="session-1",
        keychain_id="device-1",
    )
    print(f"resolved_route={resolved.to_dict()}")

    # If the client-local route fails at runtime, server code can ask for the
    # configured cloud fallback.
    fallback = manager.get_fallback_decision(
        resolved,
        keychain_id="device-1",
        reason="client_local_failed",
    )
    print(f"fallback_route={fallback.to_dict() if fallback else None}")


if __name__ == "__main__":
    main()
