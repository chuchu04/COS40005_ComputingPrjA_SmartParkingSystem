namespace WebApplication1.Models
{
    public enum TransactionType
    {
        TopUp,
        ParkingFee
    }

    public enum TransactionStatus
    {
        Pending,
        Completed,
        Failed
    }

    public enum SessionStatus
    {
        Active,
        Paid,
        Completed
    }
}
