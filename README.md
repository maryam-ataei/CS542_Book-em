#Book ‘em - Movie Ticket Booking System

##Abstract

"Book ‘em" is a modern, web-based Movie Ticket Booking System aimed at enhancing the experience of purchasing movie tickets across various cinemas. This system simplifies the process of movie selection, seat booking, and payment, providing a seamless user experience for moviegoers. By leveraging HTML, CSS, and JavaScript for the front-end, with Python and Flask managing the backend, integrated with an Oracle database, the system ensures a robust and responsive user interface.

##Features

- **Movie Discovery**: Easily find upcoming movies in a specific city or by name.
- **User Accounts**: Register and manage user profiles with distinct permissions for admins and general users.
- **Seat Booking**: View available seats, book tickets, and manage reservations.
- **Payment Processing**: Secure and efficient checkout with loyalty point integration.
- **Admin Controls**: Manage events, venues, seating arrangements, and movie listings.

##Technologies Used

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python (Flask)
- **Database**: Oracle for managing movie schedules, bookings, user registrations, and transactions.

## Key Features

- **User Registration & Profile Management**:  
  - User login, registration, and profile updates.
  
- **Movie and Showtimes Search**:  
  - Search for movies by name, city, or date.
  
- **Seat Booking**:  
  - View seat availability and book specific seats.
  
- **Payment and Checkout**:  
  - Process payments and handle customer loyalty points.
  
- **Booking History**:  
  - Retrieve past booking history and transaction details.
  
- **Event and Venue Management (Admin)**:  
  - Create, update, and manage movie events, venues, and seating arrangements.
  
- **Cancellation and Refund Processing**:  
  - Cancel bookings and process refunds with automated seat status updates.

## Database Schema

The system organizes the following key data:

- **Movies**: Name, release date, show timings, movie rating, and unique identifiers.
- **Users**: User profiles, including contact details and preferences.
- **Bookings**: Booking information, including movie details, seat numbers, and payment status.
- **Venues**: Theater capacities, seating arrangements, and pricing.

## Installation Instructions

1. Clone the repository:

    ```bash
    git clone https://github.com/maryam-ataei/CS542_FinalProject_Book-em.git
    ```

2. Navigate into the project directory:

    ```bash
    cd book-em
    ```

3. Set up the Oracle database and update your configuration files with database credentials.

5. Run the Flask application:

    ```bash
    python demo.py
    ```

6. Access the system on your local machine at `http://127.0.0.1:5000`.

## User Queries

- **Movie Discovery**: Search movies by city or name.
- **Seat Booking**: Book seats for a specific movie.
- **Payment**: Process payments securely and manage loyalty points.
- **Admin Functions**: Manage movie events, venues, and seating arrangements.

