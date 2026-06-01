import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function sendMessage(message: string) {
  try {
    const response = await axios.post(`${API_URL}/chat`, {
      message,
    });

    return response.data;
  } catch (error) {
    console.error("Chat API Error:", error);

    throw error;
  }
}
