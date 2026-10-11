import Foundation

@main
struct LeaderboardChecks {
    static func main() throws {
        let metrics: [String: Any] = ["rank": NSNull(), "score": 57, "availability_seconds": 1800.5,
                                      "credits_used": 25, "completed_tasks": 3, "images_created": 1]
        let payload: [String: Any] = ["week_start": 1791763200, "week_end": 1792368000, "server_time": 1791765000,
                                      "enabled": false, "nickname": "", "self": metrics, "entries": [],
                                      "member_count": 0, "metric": "overall"]
        func decode(_ body: [String: Any]) throws -> WeeklyBoard {
            try JSONDecoder().decode(WeeklyBoard.self, from: JSONSerialization.data(withJSONObject: body))
        }
        let privateBoard = try decode(payload)
        precondition(!privateBoard.enabled && privateBoard.nickname.isEmpty && privateBoard.personal.rank == nil)
        precondition(privateBoard.entries.isEmpty && privateBoard.personal.completed_tasks == 3)
        precondition(privateBoard.weeklyTotals.credits_used == 25 && privateBoard.personal.images_created == 1)
        precondition(BoardMetric.availability.value(privateBoard.weeklyTotals) == "30 min")
        precondition(BoardMetric.duration(45) == "<1 min" && BoardMetric.duration(0) == "0 min")
        precondition(BoardMetric.duration(3670) == "1 hr 1 min")
        var ranked = payload
        ranked["enabled"] = true; ranked["nickname"] = "Māia"; ranked["metric"] = "credits"
        var personal = metrics; personal["rank"] = 61; ranked["self"] = personal
        var entry = metrics; entry["rank"] = 1; entry["nickname"] = "Sitha"; entry["is_you"] = false
        ranked["entries"] = [entry]; ranked["member_count"] = 61
        let board = try decode(ranked)
        precondition(board.nickname == "Māia" && board.personal.rank == 61 && board.entries.count == 1)
        precondition(board.entries[0].nickname == "Sitha" && !board.entries[0].is_you)
        precondition(board.metric == .credits && board.metric.value(board.weeklyTotals) == "25")
        var gate = BoardRequestGate()
        let first = gate.begin(), second = gate.begin()
        precondition(!gate.accepts(first) && gate.accepts(second), "Old successes and errors cannot replace a new selection")
        gate.invalidate()
        precondition(!gate.accepts(second), "A profile update or identity change invalidates all old replies")
        let third = gate.begin(); precondition(gate.accepts(third))
        print("Leaderboard: private/ranked contract decoding, own rank beyond public list, duration and response fencing passed")
    }
}
