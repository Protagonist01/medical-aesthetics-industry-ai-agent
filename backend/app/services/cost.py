import os
from .supabase_client import supabase


class CostService:
    def __init__(self):
        # Pricing per 1k tokens (Mock GPT-4o)
        self.input_price = 0.005
        self.output_price = 0.015
        self.lambda_price_per_ms = 0.0000000167

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        compute_ms: int,
        session_id: str = "default",
    ):
        token_cost = (input_tokens / 1000 * self.input_price) + (
            output_tokens / 1000 * self.output_price
        )
        compute_cost = compute_ms * self.lambda_price_per_ms
        total = token_cost + compute_cost

        # Persist to Supabase
        try:
            data = {
                "session_id": session_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "compute_ms": compute_ms,
                "token_cost": token_cost,
                "compute_cost": compute_cost,
                "total_cost": total,
            }
            supabase.table("costs").insert(data).execute()
        except Exception as e:
            print(f"Failed to save cost to Supabase: {e}")

        # Return current transaction cost (cumulative is now fetched via API)
        return {
            "token_cost": token_cost,
            "compute_cost": compute_cost,
            "total_cost": total,
        }

    def get_aggregated_costs(self):
        try:
            # Fetch all records
            response = supabase.table("costs").select("*").execute()
            costs = response.data

            total_tokens_cost = sum(row["token_cost"] for row in costs)
            total_compute_cost = sum(row["compute_cost"] for row in costs)
            total_cost = sum(row["total_cost"] for row in costs)

            return {
                "total": total_cost,
                "tokens": total_tokens_cost,
                "compute": total_compute_cost,
                "storage": 0.05,  # Fixed mock value for now
            }
        except Exception as e:
            print(f"Failed to fetch costs from Supabase: {e}")
            return {"total": 0.0, "tokens": 0.0, "compute": 0.0, "storage": 0.0}


cost_service = CostService()
