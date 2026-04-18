# AI Timesheet Automation System - Frontend

This is the React frontend for the AI Timesheet Automation System. It provides an intuitive, drag-and-drop interface for users to upload their timesheet screenshots and view the extracted data.

## Tech Stack

- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Vanilla CSS with modern flex/grid layouts and CSS variables
- **HTTP Client**: Axios

## Features

- **Drag & Drop Upload Zone**: Seamless file selection and uploading.
- **Image Preview**: Interactive thumbnail of the uploaded image.
- **Results Display**: Extracted entries presented in clean, easy-to-read cards. It also displays the Raw OCR Text and JSON response.
- **Error Handling**: Graceful fallback and error alerts when API calls fail or timeout.

## Available Scripts

In the project directory, you can run:

### `npm run dev`

Runs the app in the development mode.\
Open [http://localhost:5173](http://localhost:5173) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm run build`

Builds the app for production to the `dist` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

## Design

The frontend implements modern UI/UX principles, including:
- Glassmorphism & subtle shadowing
- Smooth micro-animations for hover states
- Clear typography and responsive layout
- Graceful degradation
