import { NextResponse } from "next/server";
import { DynamoDBDocument } from "@aws-sdk/lib-dynamodb";
import { DynamoDB } from "@aws-sdk/client-dynamodb";
import { SignJWT } from "jose";

const client = DynamoDBDocument.from(
  new DynamoDB({
    region: process.env.AWS_REGION,
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
    },
  })
);

export async function POST(req: Request) {
  const { username, password } = await req.json();

  try {
    // Query DynamoDB - pk is USER#username, sk is CREDENTIALS
    const result = await client.get({
      TableName: process.env.DYNAMODB_TABLE!,
      Key: {
        pk: `USER#${username}`,
        sk: "CREDENTIALS",
      },
    });

    const user = result.Item;

    // No user found
    if (!user) {
      return NextResponse.json({ message: "Invalid credentials" }, { status: 401 });
    }

    // Plain text password check (since your DB has plain text passwords)
    if (user.password !== password) {
      return NextResponse.json({ message: "Invalid credentials" }, { status: 401 });
    }

    // Create JWT token
    const secret = new TextEncoder().encode(process.env.JWT_SECRET!);
    const token = await new SignJWT({ username: user.username, pk: user.pk })
      .setProtectedHeader({ alg: "HS256" })
      .setExpirationTime("8h")
      .sign(secret);

    // Set token as HTTP-only cookie
    const response = NextResponse.json({ success: true, username: user.username });
    response.cookies.set("auth-token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8, // 8 hours
      path: "/",
    });

    return response;
  } catch (err) {
    console.error(err);
    return NextResponse.json({ message: "Server error" }, { status: 500 });
  }
}