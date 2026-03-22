namespace WebApplication1.DTOs
{
    public class CreateTopUpRequestDto
    {
        public decimal Amount { get; set; }
    }

    public class CreateTopUpResponseDto
    {
        public long OrderCode { get; set; }
        public string PaymentUrl { get; set; } = string.Empty;
    }
}
