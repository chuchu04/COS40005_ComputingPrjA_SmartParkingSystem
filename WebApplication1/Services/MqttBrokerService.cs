using System.Text;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Client.Options;

namespace WebApplication1.Services
{
    public class MqttBrokerService
    {
        private const string SonarTopic = "parking/sensor/sonar";

        private readonly ILogger<MqttBrokerService> _logger;
        private readonly SonarProcessor _sonarProcessor;
        private readonly IMqttClient _client;
        private readonly IMqttClientOptions _options;
        private readonly SemaphoreSlim _connectionLock = new(1, 1);

        public MqttBrokerService(
            ILogger<MqttBrokerService> logger,
            SonarProcessor sonarProcessor,
            IConfiguration configuration)
        {
            _logger = logger;
            _sonarProcessor = sonarProcessor;

            var brokerHost = configuration["Mqtt:BrokerHost"] ?? throw new InvalidOperationException("Missing Mqtt:BrokerHost configuration.");
            var brokerPort = int.TryParse(configuration["Mqtt:BrokerPort"], out var parsedPort) ? parsedPort : 1883;
            var username = configuration["Mqtt:Username"] ?? throw new InvalidOperationException("Missing Mqtt:Username configuration.");
            var password = configuration["Mqtt:Password"] ?? throw new InvalidOperationException("Missing Mqtt:Password configuration.");
            var useTls = bool.TryParse(configuration["Mqtt:UseTls"], out var parsedUseTls) && parsedUseTls;

            _logger.LogInformation("MQTT configuration loaded. Host={Host}, Port={Port}, UseTls={UseTls}", brokerHost, brokerPort, useTls);

            var optionsBuilder = new MqttClientOptionsBuilder()
                .WithTcpServer(brokerHost, brokerPort)
                .WithCredentials(username, password);

            if (useTls)
            {
                optionsBuilder = optionsBuilder.WithTls();
            }

            _options = optionsBuilder.Build();

            var factory = new MqttFactory();
            _client = factory.CreateMqttClient();

            _client.UseConnectedHandler(async _ =>
            {
                _logger.LogInformation("Connected to MQTT broker. Subscribing to {Topic}", SonarTopic);
                await _client.SubscribeAsync(new TopicFilterBuilder().WithTopic(SonarTopic).Build());
                _logger.LogInformation("Subscribed to MQTT topic {Topic}", SonarTopic);
            });

            _client.UseDisconnectedHandler(_ =>
            {
                _logger.LogWarning("Disconnected from MQTT broker.");
            });

            _client.UseApplicationMessageReceivedHandler(async e =>
            {
                if (!string.Equals(e.ApplicationMessage.Topic, SonarTopic, StringComparison.OrdinalIgnoreCase))
                {
                    _logger.LogDebug("Ignoring MQTT message from non-sonar topic {Topic}", e.ApplicationMessage.Topic);
                    return;
                }

                var payloadBytes = e.ApplicationMessage.Payload;
                var payload = payloadBytes == null ? string.Empty : Encoding.UTF8.GetString(payloadBytes);

                _logger.LogInformation("Received sonar payload on {Topic}: {Payload}", SonarTopic, payload);

                try
                {
                    await _sonarProcessor.ProcessUpdateAsync(payload);
                    _logger.LogInformation("Sonar payload processed successfully.");
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to process sonar payload on topic {Topic}", SonarTopic);
                }
            });

            _ = EnsureConnectedAsync();
        }

        public async Task PublishAsync(string topic, string payload)
        {
            await EnsureConnectedAsync();

            var message = new MqttApplicationMessageBuilder()
                .WithTopic(topic)
                .WithPayload(payload)
                .WithAtLeastOnceQoS()
                .Build();

            await _client.PublishAsync(message);
        }

        private async Task EnsureConnectedAsync()
        {
            if (_client.IsConnected)
            {
                return;
            }

            await _connectionLock.WaitAsync();
            try
            {
                if (_client.IsConnected)
                {
                    return;
                }

                _logger.LogInformation("Connecting to MQTT broker...");
                await _client.ConnectAsync(_options);
                _logger.LogInformation("MQTT connection established.");
            }
            finally
            {
                _connectionLock.Release();
            }
        }
    }
}
