import SwiftUI

@main
struct PersonalAssistantApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @StateObject private var chatViewModel = ChatViewModel()
    @State private var messageText = ""
    
    var body: some View {
        NavigationView {
            VStack {
                // Lista de mensagens
                ScrollView {
                    ScrollViewReader { proxy in
                        LazyVStack(spacing: 12) {
                            ForEach(chatViewModel.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                        }
                        .padding()
                        .onChange(of: chatViewModel.messages.count) { _ in
                            if let lastMessage = chatViewModel.messages.last {
                                withAnimation {
                                    proxy.scrollTo(lastMessage.id, anchor: .bottom)
                                }
                            }
                        }
                    }
                }
                
                // Input de mensagem
                HStack {
                    TextField("Digite sua mensagem...", text: $messageText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .disabled(chatViewModel.isLoading)
                    
                    Button(action: sendMessage) {
                        if chatViewModel.isLoading {
                            ProgressView()
                        } else {
                            Image(systemName: "paperplane.fill")
                        }
                    }
                    .disabled(messageText.isEmpty || chatViewModel.isLoading)
                }
                .padding()
            }
            .navigationTitle("Assistente Pessoal")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
    
    private func sendMessage() {
        let text = messageText
        messageText = ""
        chatViewModel.sendMessage(text)
    }
}

struct MessageBubble: View {
    let message: Message
    
    var body: some View {
        HStack {
            if message.isUser {
                Spacer()
            }
            
            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                Text(message.text)
                    .padding(12)
                    .background(message.isUser ? Color.blue : Color.gray.opacity(0.2))
                    .foregroundColor(message.isUser ? .white : .primary)
                    .cornerRadius(16)
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            if !message.isUser {
                Spacer()
            }
        }
    }
}

// MARK: - Models

struct Message: Identifiable {
    let id = UUID()
    let text: String
    let isUser: Bool
    let timestamp: Date
}

// MARK: - ViewModel

class ChatViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isLoading = false
    
    private let apiEndpoint = "YOUR_API_ENDPOINT" // Substituir após deploy
    private let userId = UIDevice.current.identifierForVendor?.uuidString ?? "unknown"
    
    func sendMessage(_ text: String) {
        // Adicionar mensagem do usuário
        let userMessage = Message(text: text, isUser: true, timestamp: Date())
        messages.append(userMessage)
        
        isLoading = true
        
        // Chamar API
        guard let url = URL(string: "\(apiEndpoint)/chat") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "user_id": userId,
            "message": text
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                self?.isLoading = false
                
                if let error = error {
                    self?.addErrorMessage("Erro: \(error.localizedDescription)")
                    return
                }
                
                guard let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let responseText = json["response"] as? String else {
                    self?.addErrorMessage("Erro ao processar resposta")
                    return
                }
                
                let assistantMessage = Message(
                    text: responseText,
                    isUser: false,
                    timestamp: Date()
                )
                self?.messages.append(assistantMessage)
            }
        }.resume()
    }
    
    private func addErrorMessage(_ text: String) {
        let errorMessage = Message(text: text, isUser: false, timestamp: Date())
        messages.append(errorMessage)
    }
}

#Preview {
    ContentView()
}
