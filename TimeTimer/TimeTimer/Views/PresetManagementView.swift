//
//  PresetManagementView.swift
//  TimeTimer
//
//  Created on 2025-12-03.
//

import SwiftUI

/// Preset management view
struct PresetManagementView: View {
    @ObservedObject var viewModel: TimerViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var isEditMode = false
    
    var body: some View {
        VStack(spacing: 0) {
            headerSection
            Divider()
            listSection
            bottomSection
        }
        .frame(minWidth: 500, minHeight: 400)
    }
    
    private var headerSection: some View {
        HStack {
            Text("Manage Presets")
                .font(.title)
                .fontWeight(.bold)
            
            Spacer()
            
            Button(isEditMode ? "Done Editing" : "Edit") {
                isEditMode.toggle()
            }
            
            Button("Done") {
                dismiss()
            }
            .padding(.leading)
        }
        .padding()
    }
    
    private var listSection: some View {
        List {
            ForEach(viewModel.presets) { preset in
                self.presetRowView(preset)
            }
            .onDelete { offsets in
                if isEditMode {
                    deletePresets(at: offsets)
                }
            }
            .onMove { source, destination in
                if isEditMode {
                    movePresets(from: source, to: destination)
                }
            }
        }
    }
    
    private func presetRowView(_ preset: TimerPreset) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(preset.name)
                    .font(.headline)
                
                Text(preset.formattedDuration)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.vertical, 4)
    }
    
    private var bottomSection: some View {
        HStack {
            Button(action: {
                viewModel.resetToDefaultPresets()
            }) {
                Label("Reset to Defaults", systemImage: "arrow.counterclockwise")
            }
            .buttonStyle(PremiumButtonStyle(isDestructive: true))
            
            Spacer()
        }
        .padding()
    }
    
    private func deletePresets(at offsets: IndexSet) {
        viewModel.deletePreset(at: offsets)
    }
    
    private func movePresets(from source: IndexSet, to destination: Int) {
        viewModel.presets.move(fromOffsets: source, toOffset: destination)
        viewModel.savePresets()
    }
}
