import Foundation

@main
struct LifecycleRace {
    static func main() {
        var gate = ContributionGate()
        let firstStart = gate.beginStart()!
        // Start is awaiting HTTP when the app backgrounds. Pause finishes before
        // the delayed Start reply, then the user immediately foregrounds again.
        gate.invalidate()
        gate.beginPause()
        gate.finishPause()
        precondition(!gate.permits(firstStart, foreground: true), "Foregrounding revived a stale Start")
        precondition(gate.beginStart() == nil, "New Start overlapped a pending old Start")
        gate.finishStart()
        let explicitRestart = gate.beginStart()!
        gate.finishStart()
        precondition(gate.permits(explicitRestart, foreground: true))
        precondition(!gate.permits(firstStart, foreground: true), "Old heartbeat could affect new session")

        // Two concurrent Pause paths (scene change and user action) must both
        // finish before a new Start can be issued.
        gate.beginPause()
        gate.beginPause()
        gate.finishPause()
        precondition(gate.beginStart() == nil, "Start raced an unfinished Pause")
        gate.finishPause()
        let thirdStart = gate.beginStart()!
        gate.finishStart()
        precondition(!gate.permits(explicitRestart, foreground: true))
        precondition(gate.permits(thirdStart, foreground: true))
        precondition(!gate.permits(thirdStart, foreground: false))
        print("PASS: delayed Start, stale heartbeat, rapid foreground, and concurrent Pause regression scenarios")
    }
}
