namespace WebApplication1.Services
{
    public class GateControlService
    {
        private const string GateExitTopic = "parking/gate/exit";
        private const string PaidPayload = "PAID";
        private const string UnpaidPayload = "UNPAID";
        private readonly MqttBrokerService _mqttBrokerService;
        private readonly ILogger<GateControlService> _logger;

        public GateControlService(MqttBrokerService mqttBrokerService, ILogger<GateControlService> logger)
        {
            _mqttBrokerService = mqttBrokerService;
            _logger = logger;
        }

        public async Task OpenGateAsync()
        {
            _logger.LogInformation("Publishing gate status {Payload} to topic {Topic}", PaidPayload, GateExitTopic);
            await _mqttBrokerService.PublishAsync(GateExitTopic, PaidPayload);
        }

        public async Task NotifyUnpaidAsync()
        {
            _logger.LogInformation("Publishing gate status {Payload} to topic {Topic}", UnpaidPayload, GateExitTopic);
            await _mqttBrokerService.PublishAsync(GateExitTopic, UnpaidPayload);
        }
    };
}
