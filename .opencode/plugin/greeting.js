/**
 * PARSEC greeting plugin for opencode 1.18.13
 *
 * This is a pragmatic implementation that works within opencode's actual API.
 *
 * Key constraints discovered:
 * - console.log corrupts the TUI (stdout is the render channel)
 * - tui.showToast() doesn't render reliably
 * - session.created event fires AFTER the first user prompt
 *
 * Solution: Use the chat.message hook to prepend greeting context to the
 * first user message, so it's delivered via normal conversation flow rather
 * than a pre-input notification.
 */

const greetingMessage = `Welcome to the PARSEC RAG demo! This is a hands-on demonstration of Retrieval-Augmented Generation (RAG), where I ground my answers in a local astronomy knowledge base covering asteroid families, orbital elements, and the LSST/Rubin survey. Everything runs entirely on your machine—no API keys, no cloud account needed.

A few quick pointers:
• This is a running conversation, not a one-shot command—keep asking questions and context carries between messages
• Answers stream in as they're generated
• You may see tool calls appear mid-answer as the grounding hook retrieves facts—that's the demo working, not an error
• Press Ctrl-C or type /exit to leave

To see the grounding in action, try asking: "Why do we use proper elements to find asteroid families?" or "What causes the Kirkwood gaps?" The hook will automatically fetch relevant facts to ground my answer.

See the README for the full walkthrough. Ready to explore?`;

let greetingShown = false;

module.exports = {
  name: "parsec-greeting",
  description: "Orientation greeting for the PARSEC RAG demo",
  version: "1.0.0",

  // Hook into the chat message flow on the first user message
  async onChatMessage(message, context) {
    // Only run once per session, on the first user message
    if (greetingShown || !message || message.role !== "user") {
      return;
    }

    greetingShown = true;

    // The greeting is delivered as the assistant's first response.
    // This works by leveraging the normal chat flow rather than trying to
    // display it outside the conversation.
    if (context && context.api && context.api.chat) {
      try {
        // Prepend the greeting to the conversation history so the model sees it
        // and responds naturally to the user's first message with orientation included
        if (context.session && context.session.messages) {
          // Insert a system message before the first user message
          context.session.messages.unshift({
            role: "system",
            content: `Before answering the user's question, provide a brief, warm greeting to orient them to this demo. ${greetingMessage}`,
          });
        }
      } catch (e) {
        // Fail gracefully - don't let plugin errors break the session
      }
    }
  },

  // Alternative approach: hook into model response to prepend greeting
  async onModelResponse(response, context) {
    if (greetingShown || !response) {
      return response;
    }

    // On the first model response, prepend the greeting
    if (response.content && typeof response.content === "string") {
      greetingShown = true;
      return {
        ...response,
        content: `${greetingMessage}\n\n${response.content}`,
      };
    }

    return response;
  },

  // Hook to initialize on session start
  async initialize(context) {
    greetingShown = false;
  },
};
