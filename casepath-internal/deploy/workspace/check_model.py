"""One synthetic call to prove sign-in, the deployment and structured output.

It sends no case data. It prints only the deployment, latency, token counts
and whether the answer matched its schema. Run it only with approval.
"""
import sys

from casepath_internal.azure_model import AzureOpenAIModel, ModelError, entra_token_provider
from casepath_internal.config import load_settings
from casepath_internal.schema import choice, obj


def main():
    settings = load_settings().model
    if settings is None:
        sys.exit("No model is configured in ~/.casepath/env.")
    model = AzureOpenAIModel(settings, entra_token_provider())
    schema = obj(status=choice(["ok"]))
    try:
        result = model.respond_json(name="casepath_check", instructions="Answer with status ok.",
                                    input=[{"role": "user", "content": "Connection check. Reply with status ok."}],
                                    schema=schema, effort="low")
    except ModelError as error:
        sys.exit(f"model check failed: {error.reason} after {error.attempts} attempt(s): {error}")
    finally:
        model.close()
    print(f"deployment={result.deployment} status={result.value['status']} seconds={result.seconds} usage={result.usage}")


if __name__ == "__main__":
    main()
