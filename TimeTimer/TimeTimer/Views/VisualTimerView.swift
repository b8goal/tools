//
//  VisualTimerView.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import SwiftUI

/// Visual circular timer view
struct VisualTimerView: View {
    @ObservedObject var viewModel: TimerViewModel
    
    var body: some View {
        VStack(spacing: 30) {
            ZStack {
                // Background circle
                Circle()
                    .stroke(Color.gray.opacity(0.2), lineWidth: 20)
                    .frame(width: 280, height: 280)
                
                // Progress circle
                Circle()
                    .trim(from: 0, to: viewModel.progress)
                    .stroke(
                        ColorTheme.visualTimerGradient(progress: viewModel.progress),
                        style: StrokeStyle(lineWidth: 20, lineCap: .round)
                    )
                    .frame(width: 280, height: 280)
                    .rotationEffect(.degrees(-90))
                    .animation(.linear(duration: 1.0), value: viewModel.progress)
                
                // Time remaining in center
                VStack(spacing: 8) {
                    Text(viewModel.formattedTimeRemaining)
                        .font(.system(size: 48, weight: .medium, design: .rounded))
                        .foregroundColor(timerColor)
                        .monospacedDigit()
                    
                    Text(statusText)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            // Progress percentage
            Text("\(Int(viewModel.progress * 100))%")
                .font(.title2)
                .foregroundColor(.secondary)
        }
        .padding()
    }
    
    private var timerColor: Color {
        switch viewModel.timerState {
        case .running:
            return ColorTheme.timerRunning
        case .paused:
            return ColorTheme.timerPaused
        case .idle:
            return ColorTheme.timerIdle
        }
    }
    
    private var statusText: String {
        switch viewModel.timerState {
        case .running:
            return "Running"
        case .paused:
            return "Paused"
        case .idle:
            return "Ready"
        }
    }
}
