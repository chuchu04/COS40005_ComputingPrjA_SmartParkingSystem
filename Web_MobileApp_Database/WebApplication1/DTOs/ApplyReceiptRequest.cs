using System.ComponentModel.DataAnnotations;

namespace WebApplication1.DTOs
{
    public record ApplyReceiptRequest
    {
        [Required]
        public string ReceiptUid { get; init; } = null!;
    }
}
