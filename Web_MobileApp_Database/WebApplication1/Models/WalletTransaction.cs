using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace WebApplication1.Models
{
    public class WalletTransaction
    {
        [Key]
        public Guid Id { get; set; } = Guid.NewGuid();

        [Column(TypeName = "decimal(18,2)")]
        public decimal Amount { get; set; }

        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        public TransactionType Type { get; set; }

        public TransactionStatus Status { get; set; }

        // PayOS webhook mapping
        public long OrderCode { get; set; }

        // Foreign key to Wallet
        [Required]
        public Guid WalletId { get; set; }

        [ForeignKey("WalletId")]
        public Wallet Wallet { get; set; } = null!;
    }
}
