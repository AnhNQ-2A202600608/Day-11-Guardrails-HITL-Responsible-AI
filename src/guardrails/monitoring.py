class MonitoringAlert:
    """Monitoring and alerting module for safety pipeline metrics.
    Checks plugin stats and triggers alerts if block rates or rate limit hits exceed thresholds.
    """
    def __init__(self, rate_limit_plugin=None, input_plugin=None, output_plugin=None):
        self.rate_limit_plugin = rate_limit_plugin
        self.input_plugin = input_plugin
        self.output_plugin = output_plugin

    def check_metrics(self):
        # Gather metrics from various plugins
        total_requests = 0
        blocked_requests = 0
        rate_limit_hits = 0
        judge_fails = 0
        
        if self.rate_limit_plugin:
            rate_limit_hits = self.rate_limit_plugin.rate_limit_hits
            
        if self.input_plugin:
            total_requests = self.input_plugin.total_count
            blocked_requests += self.input_plugin.blocked_count
            
        if self.output_plugin:
            blocked_requests += self.output_plugin.blocked_count
            judge_fails = self.output_plugin.blocked_count  # since LLM safety judge failure causes output blocks
            
        # Calculate rates
        block_rate = (blocked_requests / total_requests) if total_requests > 0 else 0.0
        
        print("\n" + "=" * 60)
        print("MONITORING METRICS DASHBOARD")
        print("=" * 60)
        print(f"  Total user requests:      {total_requests}")
        print(f"  Total blocked requests:   {blocked_requests} ({block_rate:.1%})")
        print(f"  Rate limiter hits:        {rate_limit_hits}")
        print(f"  Safety Judge failures:    {judge_fails}")
        print("=" * 60)

        # Alerts thresholds checks
        alerts = []
        if block_rate > 0.30:
            alerts.append(f"ALERT: High security block rate detected! ({block_rate:.1%} of requests blocked, threshold is 30%)")
        if rate_limit_hits > 2:
            alerts.append(f"ALERT: Potential DDoS / Abuse detected! ({rate_limit_hits} rate limit hits recorded)")
        if judge_fails > 3:
            alerts.append(f"ALERT: High safety judge failure rate! ({judge_fails} outputs failed safety evaluation)")

        if alerts:
            print("\nSYSTEM ALERTS TRIGGERED:")
            for alert in alerts:
                print(f"  {alert}")
            print("=" * 60)
        else:
            print("  System Status: Healthy (All metrics within normal bounds)\n")
